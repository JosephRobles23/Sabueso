"""Flow pe_seace — contratos peruanos OCDS (Open Contracting Partnership bulk dumps).

Fuente:
  Open Contracting Partnership publica los datos del SEACE peruano en formato
  OCDS JSON-Lines comprimido. Sin auth, licencia CC BY 4.0.

  Por año (SEACE_YEARS comma-sep, default '2024,2025,2026'):
    https://data.open-contracting.org/en/publication/135/download?name=YYYY.jsonl.gz

  Override total via SEACE_DUMP_URLS (comma-sep) si OCP cambia el path.

Streaming:
  Bajamos el .gz con httpx en streaming → descomprimimos con gzip → parseamos
  línea por línea. NO cargamos el JSONL completo en memoria (cada año ~160MB
  descomprimido).

Filtros del scope:
  - Buyer ruc whitelist: MINSA, MEF, MTC, ESSALUD + top 10 gob. regionales
    (SEACE_BUYER_RUC override). El filtro se aplica al parsear cada release.
  - SEACE_BUYER_RUC=all desactiva el filtro (procesa todo).

Por cada contrato (release OCDS con awards o contracts):
  - entity tipo `contract` (identifier=OCID, embedding del título)
  - entity tipo `company` (identifier=RUC adjudicado)
  - entity tipo `government_entity` (identifier=RUC comprador)
  - edges: company --awarded--> contract, government_entity --procured--> contract,
           company --counterparty--> government_entity
  - claims: amount, signature_date

Incremental: checkpoint por OCID en pipeline_checkpoints (flow_id='pe_seace').
"""

from __future__ import annotations

import asyncio
import gzip
import io
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from .common import upsert
from .common.db import checkpoint_done, checkpoint_save, close_pool
from .common.embedding import embed_batch
from .common.logging import configure as configure_logging
from .common.logging import get_logger

log = get_logger("sabueso.pipeline.pe_seace")

FLOW_ID = "pe_seace"
DEFAULT_BASE = "https://data.open-contracting.org/en/publication/135/download?name={year}.jsonl.gz"
DEFAULT_YEARS = "2024,2025,2026"
BATCH_SIZE = 32

# Los OCDS bulk dumps usan IDs internos cortos (no RUCs de 11 dígitos), así que
# filtramos por substring del buyer_name. SEACE_BUYER_RUC sigue disponible para
# filtrar por el id real cuando el caller lo necesita.
DEFAULT_BUYER_NAME_TERMS = [
    "MINSA",
    "MINISTERIO DE SALUD",
    "MINISTERIO DE ECONOMIA",
    "MEF",
    "MINISTERIO DE TRANSPORTES",
    "MTC",
    "ESSALUD",
    "SEGURO SOCIAL",
    "GOBIERNO REGIONAL",
    "PETROLEOS DEL PERU",
    "PETROPERU",
    "EJERCITO PERUANO",
    "MARINA DE GUERRA",
    "FUERZA AEREA",
]


@dataclass(slots=True)
class Release:
    ocid: str
    title: str
    buyer_name: str
    buyer_ruc: str | None
    supplier_name: str | None
    supplier_ruc: str | None
    amount: float | None
    currency: str | None
    date: str | None
    url: str | None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _dump_urls() -> list[str]:
    override = os.environ.get("SEACE_DUMP_URLS")
    if override:
        return [u.strip() for u in override.split(",") if u.strip()]
    years = os.environ.get("SEACE_YEARS", DEFAULT_YEARS).split(",")
    template = os.environ.get("SEACE_DUMP_URL_TEMPLATE", DEFAULT_BASE)
    return [template.format(year=y.strip()) for y in years if y.strip()]


@dataclass(slots=True)
class BuyerFilter:
    rucs: set[str] | None       # None = no RUC filter
    name_terms: list[str] | None  # None = no name filter

    def matches(self, release: "Release") -> bool:
        if self.rucs is None and self.name_terms is None:
            return True  # passthrough
        if self.rucs is not None and release.buyer_ruc in self.rucs:
            return True
        if self.name_terms is not None and release.buyer_name:
            upper = release.buyer_name.upper()
            for term in self.name_terms:
                if term in upper:
                    return True
        return False


def _buyer_filter() -> BuyerFilter:
    """Construye el filtro de buyers.

    Precedencia:
      SEACE_BUYER_RUC=all                       → sin filtro
      SEACE_BUYER_RUC=<ids comma-sep>           → filtra por ids
      SEACE_BUYER_NAMES=<terms comma-sep>       → filtra por substring nombre
      sin env                                   → DEFAULT_BUYER_NAME_TERMS
    """
    ruc_env = os.environ.get("SEACE_BUYER_RUC")
    name_env = os.environ.get("SEACE_BUYER_NAMES")
    if ruc_env and ruc_env.strip().lower() == "all":
        return BuyerFilter(rucs=None, name_terms=None)
    rucs = None
    if ruc_env:
        rucs = {r.strip() for r in ruc_env.split(",") if r.strip()}
    names = None
    if name_env:
        names = [n.strip().upper() for n in name_env.split(",") if n.strip()]
    elif rucs is None:
        names = [t.upper() for t in DEFAULT_BUYER_NAME_TERMS]
    return BuyerFilter(rucs=rucs, name_terms=names)


# ---------------------------------------------------------------------------
# Streaming download + jsonl parse
# ---------------------------------------------------------------------------
async def _stream_jsonl(url: str) -> AsyncIterator[dict[str, Any]]:
    """Baja .jsonl.gz en streaming, descomprime y emite cada release como dict.

    Implementación: descargamos chunks, los acumulamos en un BytesIO temporal y
    descomprimimos progresivamente. Para 150-200MB es cómodo en memoria con 4Gi.
    """
    log.info("pe_seace.download_start", url=url)
    timeout = httpx.Timeout(600.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
        async with c.stream("GET", url) as resp:
            if resp.status_code != 200:
                log.error("pe_seace.download_failed", url=url, status=resp.status_code)
                return
            buf = io.BytesIO()
            downloaded = 0
            async for chunk in resp.aiter_bytes(chunk_size=1 << 20):  # 1MB
                buf.write(chunk)
                downloaded += len(chunk)
            log.info("pe_seace.download_done", url=url, bytes=downloaded)
    buf.seek(0)

    # Itera líneas; muchos dumps OCDS son un release por línea
    line_count = 0
    with gzip.GzipFile(fileobj=buf, mode="rb") as gz:
        for raw_line in gz:
            line_count += 1
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if line_count <= 3:
                    log.warning("pe_seace.json_decode_failed", line_no=line_count)
                continue
            # Cada línea puede ser un release, o un release-package
            if "releases" in obj and isinstance(obj["releases"], list):
                for rel in obj["releases"]:
                    yield rel
            elif "ocid" in obj:
                yield obj


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _resolve_ruc(party_id: Any, parties: list[dict]) -> str | None:
    if party_id is None:
        return None
    for p in parties:
        if p.get("id") == party_id:
            ident = (p.get("identifier") or {}).get("id")
            if ident:
                return str(ident)
            break
    if str(party_id).isdigit():
        return str(party_id)
    return None


def _parse_release(rel: dict[str, Any]) -> Release | None:
    ocid = rel.get("ocid")
    if not ocid:
        return None
    tender = rel.get("tender") or {}
    awards = rel.get("awards") or []
    contracts = rel.get("contracts") or []
    buyer = rel.get("buyer") or {}
    parties = rel.get("parties") or []

    title = tender.get("title") or rel.get("title") or str(ocid)
    buyer_name = buyer.get("name") or ""
    buyer_ruc = _resolve_ruc(buyer.get("id"), parties)

    supplier_name = None
    supplier_ruc = None
    amount = None
    currency = None
    date = None

    if awards:
        first_award = awards[0]
        suppliers = first_award.get("suppliers") or []
        if suppliers:
            supplier_name = suppliers[0].get("name")
            supplier_ruc = _resolve_ruc(suppliers[0].get("id"), parties)
        value = first_award.get("value") or {}
        amount = value.get("amount")
        currency = value.get("currency")
        date = first_award.get("date") or rel.get("date")
    elif contracts:
        c0 = contracts[0]
        value = c0.get("value") or {}
        amount = value.get("amount")
        currency = value.get("currency")
        date = c0.get("dateSigned") or rel.get("date")

    return Release(
        ocid=str(ocid),
        title=str(title)[:500],
        buyer_name=buyer_name,
        buyer_ruc=buyer_ruc,
        supplier_name=supplier_name,
        supplier_ruc=supplier_ruc,
        amount=float(amount) if amount is not None else None,
        currency=currency,
        date=date,
        url=rel.get("url") or f"https://contratacionesabiertas.osce.gob.pe/contrato/{ocid}",
    )


async def _iter_all_releases() -> AsyncIterator[Release]:
    bf = _buyer_filter()
    log.info(
        "pe_seace.config",
        urls=_dump_urls(),
        ruc_filter=(None if bf.rucs is None else len(bf.rucs)),
        name_filter=(None if bf.name_terms is None else len(bf.name_terms)),
    )
    for url in _dump_urls():
        kept = 0
        skipped_filter = 0
        async for raw in _stream_jsonl(url):
            release = _parse_release(raw)
            if release is None:
                continue
            if not bf.matches(release):
                skipped_filter += 1
                continue
            kept += 1
            yield release
        log.info("pe_seace.dump_done", url=url, kept=kept, skipped_filter=skipped_filter)


# ---------------------------------------------------------------------------
# Upserting
# ---------------------------------------------------------------------------
async def _process_batch(batch: list[Release]) -> tuple[int, int]:
    pending: list[Release] = []
    skipped = 0
    for r in batch:
        if await checkpoint_done(FLOW_ID, r.ocid):
            skipped += 1
            continue
        pending.append(r)
    if not pending:
        return 0, skipped

    try:
        embeddings = await embed_batch([r.title for r in pending])
    except Exception as e:
        log.error("pe_seace.embed_batch_failed", error=str(e))
        for r in pending:
            await checkpoint_save(FLOW_ID, r.ocid, "failed", error=f"embed: {e}")
        return 0, skipped

    processed = 0
    for r, emb in zip(pending, embeddings):
        try:
            source_id = await upsert.upsert_source(
                upsert.SourceUpsert(
                    url=r.url or f"seace://{r.ocid}",
                    source_type="seace",
                    title=r.title,
                    country="pe",
                )
            )
            contract_entity = await upsert.upsert_entity(
                upsert.EntityUpsert(
                    country="pe",
                    type="contract",
                    identifier=r.ocid,
                    name=r.title,
                    metadata={
                        "buyer_name": r.buyer_name,
                        "supplier_name": r.supplier_name,
                        "amount": r.amount,
                        "currency": r.currency,
                        "date": r.date,
                        "source": "seace-ocp",
                    },
                    embedding=emb,
                )
            )
            buyer_entity = None
            if r.buyer_ruc:
                buyer_entity = await upsert.upsert_entity(
                    upsert.EntityUpsert(
                        country="pe",
                        type="government_entity",
                        identifier=r.buyer_ruc,
                        name=r.buyer_name or r.buyer_ruc,
                    )
                )
            supplier_entity = None
            if r.supplier_ruc:
                supplier_entity = await upsert.upsert_entity(
                    upsert.EntityUpsert(
                        country="pe",
                        type="company",
                        identifier=r.supplier_ruc,
                        name=r.supplier_name or r.supplier_ruc,
                    )
                )
            if r.amount is not None:
                await upsert.insert_claim(
                    upsert.ClaimUpsert(
                        entity_id=contract_entity,
                        predicate="amount",
                        object_value={"value": r.amount, "currency": r.currency},
                        source_id=source_id,
                        agent_callsign="sabueso-pipeline/seace",
                        confidence=0.99,
                    )
                )
            if r.date:
                await upsert.insert_claim(
                    upsert.ClaimUpsert(
                        entity_id=contract_entity,
                        predicate="signature_date",
                        object_value={"date": r.date},
                        source_id=source_id,
                        agent_callsign="sabueso-pipeline/seace",
                        confidence=0.99,
                    )
                )
            if buyer_entity is not None:
                await upsert.upsert_edge(
                    upsert.EdgeUpsert(
                        from_entity=buyer_entity,
                        to_entity=contract_entity,
                        type="procured",
                        agent_callsign="sabueso-pipeline/seace",
                    )
                )
            if supplier_entity is not None:
                await upsert.upsert_edge(
                    upsert.EdgeUpsert(
                        from_entity=supplier_entity,
                        to_entity=contract_entity,
                        type="awarded",
                        agent_callsign="sabueso-pipeline/seace",
                    )
                )
                if buyer_entity is not None:
                    await upsert.upsert_edge(
                        upsert.EdgeUpsert(
                            from_entity=supplier_entity,
                            to_entity=buyer_entity,
                            type="counterparty",
                            agent_callsign="sabueso-pipeline/seace",
                        )
                    )
            await checkpoint_save(
                FLOW_ID,
                r.ocid,
                "ok",
                metadata={
                    "amount": r.amount,
                    "buyer": r.buyer_name,
                    "supplier": r.supplier_name,
                },
            )
            processed += 1
        except Exception as e:
            log.warning("pe_seace.upsert_failed", ocid=r.ocid, error=str(e))
            await checkpoint_save(FLOW_ID, r.ocid, "failed", error=str(e))
    return processed, skipped


async def _chunked(stream: AsyncIterator[Release], size: int) -> AsyncIterator[list[Release]]:
    buf: list[Release] = []
    async for item in stream:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


async def run() -> int:
    configure_logging()
    log.info("pe_seace.start")
    total_processed = 0
    total_skipped = 0
    total_seen = 0
    async for batch in _chunked(_iter_all_releases(), BATCH_SIZE):
        total_seen += len(batch)
        processed, skipped = await _process_batch(batch)
        total_processed += processed
        total_skipped += skipped
        if total_seen % (BATCH_SIZE * 20) == 0:
            log.info(
                "pe_seace.progress",
                seen=total_seen,
                processed=total_processed,
                skipped=total_skipped,
            )
    log.info(
        "pe_seace.done",
        seen=total_seen,
        processed=total_processed,
        skipped=total_skipped,
    )
    await close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
