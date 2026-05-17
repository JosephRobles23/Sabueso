"""Flow pe_jne_pdfs — Hojas de Vida JNE 2026 (225 candidatos).

Fuente:
  Plataforma electoral JNE — listado de candidatos + PDF de hoja de vida por cada uno.
  Endpoint base configurable via JNE_API_BASE_URL. Si el endpoint cambia,
  expón los nuevos URLs con esa env var; el flow no asume estructura HTML.

Lo que hace por cada candidato:
  1. Descarga el PDF (con throttle 1 PDF/3s si JNE_THROTTLE_SECONDS está set).
  2. Sube a GCS `sabueso-jne-pdfs-hack` (env GCS_BUCKET_JNE_PDFS).
  3. Extrae texto con PyMuPDF + fallback Tika.
  4. Crea entity tipo `person` con identifier=DNI (o expediente si DNI falta).
  5. Embedding del texto extraído (primeros 6K chars — suficiente para semantic search).
  6. Claims:
        - candidatura (cargo, organización política)
        - estudios (parseado heurístico)
        - patrimonio (parseado heurístico, captura monto si aparece)
        - cargos previos (parseado heurístico)

Re-corrida: checkpoint por expediente JNE en pipeline_checkpoints
(flow_id='pe_jne_pdfs').
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import upsert
from .common.db import checkpoint_done, checkpoint_save, close_pool
from .common.embedding import embed_one
from .common.extract import extract
from .common.gcs import gs_uri, upload_bytes
from .common.http import client, get_with_retries
from .common.logging import configure as configure_logging
from .common.logging import get_logger

log = get_logger("sabueso.pipeline.pe_jne_pdfs")

FLOW_ID = "pe_jne_pdfs"
DEFAULT_BASE_URL = "https://plataformaelectoral.jne.gob.pe/api"
DEFAULT_THROTTLE_SECONDS = 3.0
DEFAULT_BUCKET = "sabueso-jne-pdfs-hack"
EMBED_MAX_CHARS = 6000


# ---------------------------------------------------------------------------
# Listado de candidatos
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Candidate:
    expediente: str
    dni: str | None
    full_name: str
    cargo: str  # 'presidente'|'congresista'|'vicepresidente'|...
    organizacion: str | None
    pdf_url: str
    meta: dict[str, Any]


def _candidates_local_file() -> Path | None:
    p = os.environ.get("JNE_CANDIDATES_FILE")
    return Path(p) if p else None


async def _fetch_candidates() -> list[Candidate]:
    """Lee el listado de candidatos.

    Dos modos:
      A) JNE_CANDIDATES_FILE → JSON local con la lista (preferido para reproducibilidad).
      B) JNE_API_BASE_URL    → endpoint que devuelve `{ candidates: [...] }`.
         Si el endpoint real cambia, ajustar el parser acá.
    """
    local = _candidates_local_file()
    if local and local.exists():
        log.info("pe_jne.candidates_local", file=str(local))
        data = json.loads(local.read_text(encoding="utf-8"))
        return _parse_candidates(data)

    base_url = os.environ.get("JNE_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    log.info("pe_jne.candidates_fetch", base_url=base_url)
    async with client(timeout=60.0) as c:
        # El endpoint puede ser /candidatos/2026 o /elecciones/2026/candidatos.
        # Probamos ambos.
        for path in ("/candidatos/2026", "/elecciones/2026/candidatos"):
            resp = await get_with_retries(c, f"{base_url}{path}", accept_status=(200,))
            if resp.status_code == 200:
                try:
                    return _parse_candidates(resp.json())
                except json.JSONDecodeError:
                    continue
    log.warning("pe_jne.candidates_empty")
    return []


def _parse_candidates(data: Any) -> list[Candidate]:
    """Acepta dos shapes razonables:
       - {"candidates": [...]}
       - [...]  (list directa)
    """
    items: list[dict] = []
    if isinstance(data, dict):
        items = data.get("candidates") or data.get("results") or []
    elif isinstance(data, list):
        items = data
    out: list[Candidate] = []
    for raw in items:
        expediente = str(
            raw.get("expediente") or raw.get("idHojaVida") or raw.get("id") or ""
        ).strip()
        if not expediente:
            continue
        full_name = raw.get("nombre_completo") or (
            (raw.get("nombres", "") + " " + raw.get("apellidos", "")).strip()
        )
        organizacion = (
            raw.get("organizacion")
            or raw.get("partido")
            or raw.get("organizacionPolitica")
        )
        out.append(
            Candidate(
                expediente=expediente,
                dni=(raw.get("dni") or raw.get("numeroDocumento") or "").strip() or None,
                full_name=full_name.strip(),
                cargo=str(raw.get("cargo") or raw.get("eleccion") or "").lower(),
                organizacion=organizacion,
                pdf_url=raw.get("pdf_url") or raw.get("urlHojaVida") or "",
                meta={k: v for k, v in raw.items() if k not in {"dni", "nombre_completo"}},
            )
        )
    return out


# ---------------------------------------------------------------------------
# PDF download + extract + parse
# ---------------------------------------------------------------------------
async def _download_pdf(c, url: str) -> bytes | None:
    resp = await get_with_retries(c, url, accept_status=(200,))
    if resp.status_code != 200:
        log.warning("pe_jne.pdf_failed", url=url, status=resp.status_code)
        return None
    return resp.content


def _parse_hoja_vida(text: str) -> dict[str, Any]:
    """Parser heurístico mínimo. No intenta cubrir todo el formulario JNE — solo
    extrae los campos más frecuentes para los claims."""
    out: dict[str, Any] = {}

    # Patrimonio: busca "Patrimonio" + monto en S/. (soles)
    m = re.search(r"Patrimonio[^S/]{0,40}S/\.?\s*([\d.,]+)", text, flags=re.IGNORECASE)
    if m:
        try:
            value = float(m.group(1).replace(".", "").replace(",", "."))
            out["patrimonio_pen"] = value
        except ValueError:
            pass

    # Estudios: las hojas de vida JNE listan secciones tipo "FORMACIÓN ACADÉMICA"
    m = re.search(
        r"FORMACI[ÓO]N\s+ACAD[ÉE]MICA[\s\S]{0,2500}?(?=EXPERIENCIA|CARGOS|TRAYECTORIA|DECLARACI[ÓO]N|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        out["formacion_text"] = m.group(0)[:2000]

    # Cargos previos
    m = re.search(
        r"(CARGOS\s+P[ÚU]BLICOS|EXPERIENCIA\s+LABORAL)[\s\S]{0,2500}?(?=DECLARACI[ÓO]N|SENTENCIAS|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        out["cargos_text"] = m.group(0)[:2000]

    # Sentencias (campo penal/civil)
    m = re.search(
        r"SENTENCIAS[\s\S]{0,1500}?(?=DECLARACI[ÓO]N|RENUNCIAS|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        out["sentencias_text"] = m.group(0)[:1500]

    return out


async def _process_candidate(cand: Candidate, c) -> bool:
    if not cand.pdf_url:
        log.warning("pe_jne.candidate_no_pdf", expediente=cand.expediente)
        await checkpoint_save(FLOW_ID, cand.expediente, "skipped", error="no pdf_url")
        return False

    if await checkpoint_done(FLOW_ID, cand.expediente):
        return False  # ya estaba listo

    bucket = os.environ.get("GCS_BUCKET_JNE_PDFS", DEFAULT_BUCKET)
    blob_name = f"2026/{cand.expediente}.pdf"
    pdf_bytes = await _download_pdf(c, cand.pdf_url)
    if pdf_bytes is None:
        await checkpoint_save(FLOW_ID, cand.expediente, "failed", error="download failed")
        return False

    content_hash = hashlib.sha256(pdf_bytes).hexdigest()

    try:
        await upload_bytes(bucket, blob_name, pdf_bytes, content_type="application/pdf")
    except Exception as e:
        log.warning("pe_jne.gcs_upload_failed", expediente=cand.expediente, error=str(e))
        await checkpoint_save(FLOW_ID, cand.expediente, "failed", error=f"gcs: {e}")
        return False
    storage_uri = gs_uri(bucket, blob_name)

    # Extracción en archivo temporal local
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        tmp_path = tf.name
    try:
        result = extract(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    parsed = _parse_hoja_vida(result.text)
    embed_input = (cand.full_name + "\n\n" + result.text)[:EMBED_MAX_CHARS]
    try:
        embedding = await embed_one(embed_input)
    except Exception as e:
        log.warning("pe_jne.embed_failed", expediente=cand.expediente, error=str(e))
        embedding = None

    source_id = await upsert.upsert_source(
        upsert.SourceUpsert(
            url=cand.pdf_url,
            source_type="jne",
            title=f"Hoja de Vida JNE 2026 — {cand.full_name}",
            content_hash=content_hash,
            content_storage=storage_uri,
            country="pe",
        )
    )

    person_identifier = cand.dni or f"JNE-{cand.expediente}"
    person_entity = await upsert.upsert_entity(
        upsert.EntityUpsert(
            country="pe",
            type="person",
            identifier=person_identifier,
            name=cand.full_name,
            metadata={
                "expediente_jne": cand.expediente,
                "cargo_2026": cand.cargo,
                "organizacion_politica": cand.organizacion,
                "hoja_vida_pages": result.pages,
                "hoja_vida_method": result.method,
            },
            embedding=embedding,
        )
    )

    await upsert.insert_claim(
        upsert.ClaimUpsert(
            entity_id=person_entity,
            predicate="candidatura_2026",
            object_value={"cargo": cand.cargo, "organizacion": cand.organizacion},
            source_id=source_id,
            agent_callsign="sabueso-pipeline/jne",
            confidence=0.99,
        )
    )
    if "patrimonio_pen" in parsed:
        await upsert.insert_claim(
            upsert.ClaimUpsert(
                entity_id=person_entity,
                predicate="patrimonio_declarado",
                object_value={"value": parsed["patrimonio_pen"], "currency": "PEN"},
                source_id=source_id,
                agent_callsign="sabueso-pipeline/jne",
                confidence=0.85,
            )
        )
    if "formacion_text" in parsed:
        await upsert.insert_claim(
            upsert.ClaimUpsert(
                entity_id=person_entity,
                predicate="formacion_academica",
                object_value={"raw": parsed["formacion_text"]},
                source_id=source_id,
                source_extract=parsed["formacion_text"][:480],
                agent_callsign="sabueso-pipeline/jne",
                confidence=0.8,
            )
        )
    if "cargos_text" in parsed:
        await upsert.insert_claim(
            upsert.ClaimUpsert(
                entity_id=person_entity,
                predicate="cargos_previos",
                object_value={"raw": parsed["cargos_text"]},
                source_id=source_id,
                source_extract=parsed["cargos_text"][:480],
                agent_callsign="sabueso-pipeline/jne",
                confidence=0.8,
            )
        )
    if "sentencias_text" in parsed:
        await upsert.insert_claim(
            upsert.ClaimUpsert(
                entity_id=person_entity,
                predicate="sentencias_judiciales",
                object_value={"raw": parsed["sentencias_text"]},
                source_id=source_id,
                source_extract=parsed["sentencias_text"][:480],
                agent_callsign="sabueso-pipeline/jne",
                confidence=0.8,
            )
        )

    await checkpoint_save(
        FLOW_ID,
        cand.expediente,
        "ok",
        metadata={
            "name": cand.full_name,
            "cargo": cand.cargo,
            "pages": result.pages,
            "extract_method": result.method,
            "gcs": storage_uri,
        },
    )
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def _candidate_stream(candidates: list[Candidate]) -> AsyncIterator[Candidate]:
    throttle = float(os.environ.get("JNE_THROTTLE_SECONDS", str(DEFAULT_THROTTLE_SECONDS)))
    first = True
    for cand in candidates:
        if not first and throttle > 0:
            await asyncio.sleep(throttle)
        first = False
        yield cand


async def run() -> int:
    configure_logging()
    if os.environ.get("JNE_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        log.info("pe_jne.skipped", reason="JNE_ENABLED!=true (default for hackathon)")
        await close_pool()
        return 0
    log.info("pe_jne.start")
    candidates = await _fetch_candidates()
    log.info("pe_jne.candidates_discovered", count=len(candidates))

    processed = 0
    skipped = 0
    failed = 0
    async with client(timeout=120.0) as c:
        async for cand in _candidate_stream(candidates):
            if await checkpoint_done(FLOW_ID, cand.expediente):
                skipped += 1
                continue
            try:
                ok = await _process_candidate(cand, c)
                if ok:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                log.error("pe_jne.process_error", expediente=cand.expediente, error=str(e))
                await checkpoint_save(FLOW_ID, cand.expediente, "failed", error=str(e))
                failed += 1
            if (processed + failed) % 10 == 0:
                log.info("pe_jne.progress", processed=processed, skipped=skipped, failed=failed)

    log.info("pe_jne.done", processed=processed, skipped=skipped, failed=failed)
    await close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
