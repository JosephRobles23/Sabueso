"""Flow pe_legalize — ingesta de normas peruanas (legalize-pe, 1,617 normas).

Fuente:
  - Repo: github.com/crafter-research/legalize-pe (markdown + front-matter YAML)
  - Path: `leyes/pe/*.md`
  - Configurable via LEGALIZE_PE_REPO_URL / LEGALIZE_PE_LOCAL_DIR.

Front-matter esperado (en español):
  ---
  titulo: "..."
  identificador: "articulo-1-codigo-civil"
  rango: "articulo"|"ley"|"decreto"
  fechaPublicacion: "2023-01-15"
  estado: "vigente"|"derogada"|"modificada"
  fuente: "https://..."
  sumilla: "..."           # base del embedding junto al título
  materias: ["civil", ...]
  ---
  <markdown body>

Cada norma → entity tipo `law` (UNIQUE country='pe', type='law', identifier).
Embedding sobre `titulo + sumilla`. Idempotente por checkpoint.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

import yaml

from .common import upsert
from .common.db import checkpoint_done, checkpoint_save, close_pool
from .common.embedding import embed_batch
from .common.logging import configure as configure_logging
from .common.logging import get_logger

log = get_logger("sabueso.pipeline.pe_legalize")

FLOW_ID = "pe_legalize"
DEFAULT_REPO = "https://github.com/crafter-research/legalize-pe.git"
DEFAULT_GLOB = "leyes/pe/*.md"
CLONE_DIR = Path(os.environ.get("PIPELINE_TMP", "/tmp")) / "legalize-pe"
BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Source discovery
# ---------------------------------------------------------------------------
def _local_dir() -> Path | None:
    p = os.environ.get("LEGALIZE_PE_LOCAL_DIR")
    return Path(p) if p else None


def _clone_or_pull(target: Path, repo_url: str) -> None:
    if target.exists() and (target / ".git").exists():
        log.info("pe_legalize.git_pull", target=str(target))
        subprocess.run(["git", "-C", str(target), "pull", "--ff-only"], check=True)
        return
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("pe_legalize.git_clone", repo=repo_url, target=str(target))
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target)], check=True)


def _discover_sources() -> Path:
    local = _local_dir()
    if local and local.exists():
        log.info("pe_legalize.source_local", dir=str(local))
        return local
    repo_url = os.environ.get("LEGALIZE_PE_REPO_URL", DEFAULT_REPO)
    _clone_or_pull(CLONE_DIR, repo_url)
    return CLONE_DIR


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Splits `---\\nyaml\\n---\\nbody`. Devuelve ({}, text) si no hay front-matter."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    yaml_block = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(yaml_block) or {}
        if not isinstance(meta, dict):
            return {}, text
        return meta, body
    except yaml.YAMLError as e:
        log.warning("pe_legalize.yaml_parse_failed", error=str(e))
        return {}, text


def _year_from_date(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None


def _parse_md_law(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("pe_legalize.read_failed", path=str(path), error=str(e))
        return None
    meta, _body = _parse_frontmatter(text)
    law_id = meta.get("identificador") or path.stem
    title = meta.get("titulo") or meta.get("title")
    if not law_id or not title:
        return None
    materias = meta.get("materias") or []
    if isinstance(materias, str):
        materias = [m.strip() for m in materias.split(",") if m.strip()]
    return {
        "law_id": str(law_id).strip(),
        "title": str(title).strip(),
        "summary": str(meta.get("sumilla") or "").strip(),
        "year": _year_from_date(meta.get("fechaPublicacion") or meta.get("ultimaActualizacion")),
        "url": meta.get("fuente") or meta.get("fuenteAlternativa"),
        "rango": meta.get("rango"),
        "estado": meta.get("estado"),
        "materias": materias,
    }


def _iter_laws(root: Path) -> Iterable[dict]:
    glob = os.environ.get("LEGALIZE_PE_GLOB", DEFAULT_GLOB)
    seen_ids: set[str] = set()
    for path in sorted(root.glob(glob)):
        if path.name.startswith(".") or not path.is_file():
            continue
        law = _parse_md_law(path)
        if law is None:
            continue
        if law["law_id"] in seen_ids:
            continue
        seen_ids.add(law["law_id"])
        yield law


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
async def _process_batch(batch: list[dict]) -> tuple[int, int]:
    """Embeds + upserts un batch. Devuelve (procesados, saltados)."""
    # Filtra los que ya están en checkpoint
    pending: list[dict] = []
    skipped = 0
    for law in batch:
        if await checkpoint_done(FLOW_ID, law["law_id"]):
            skipped += 1
            continue
        pending.append(law)

    if not pending:
        return 0, skipped

    embed_inputs = [f"{law['title']}\n\n{law['summary']}".strip() for law in pending]
    try:
        embeddings = await embed_batch(embed_inputs)
    except Exception as e:
        log.error("pe_legalize.embed_batch_failed", error=str(e), size=len(pending))
        for law in pending:
            await checkpoint_save(FLOW_ID, law["law_id"], "failed", error=f"embed: {e}")
        return 0, skipped

    processed = 0
    for law, emb in zip(pending, embeddings):
        try:
            source_id = await upsert.upsert_source(
                upsert.SourceUpsert(
                    url=law.get("url") or f"legalize-pe://{law['law_id']}",
                    source_type="legalize",
                    title=law["title"],
                    country="pe",
                )
            )
            entity_id = await upsert.upsert_entity(
                upsert.EntityUpsert(
                    country="pe",
                    type="law",
                    identifier=law["law_id"],
                    name=law["title"],
                    aliases=law.get("materias") or [],
                    metadata={
                        "year": law.get("year"),
                        "summary": law.get("summary"),
                        "rango": law.get("rango"),
                        "estado": law.get("estado"),
                        "source": "legalize-pe",
                    },
                    embedding=emb,
                )
            )
            if law.get("summary"):
                await upsert.insert_claim(
                    upsert.ClaimUpsert(
                        entity_id=entity_id,
                        predicate="summary",
                        object_value={"text": law["summary"]},
                        source_id=source_id,
                        source_extract=law["summary"][:480],
                        agent_callsign="sabueso-pipeline/legalize",
                    )
                )
            await checkpoint_save(
                FLOW_ID,
                law["law_id"],
                "ok",
                metadata={"title": law["title"], "year": law.get("year")},
            )
            processed += 1
        except Exception as e:
            log.warning("pe_legalize.upsert_failed", law_id=law["law_id"], error=str(e))
            await checkpoint_save(FLOW_ID, law["law_id"], "failed", error=str(e))
    return processed, skipped


async def _chunked(stream: Iterable[dict], size: int) -> AsyncIterator[list[dict]]:
    buf: list[dict] = []
    for item in stream:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


async def run() -> int:
    configure_logging()
    log.info("pe_legalize.start")
    root = _discover_sources()
    laws = list(_iter_laws(root))
    log.info("pe_legalize.discovered", count=len(laws))

    total_processed = 0
    total_skipped = 0
    async for batch in _chunked(laws, BATCH_SIZE):
        processed, skipped = await _process_batch(batch)
        total_processed += processed
        total_skipped += skipped
        log.info(
            "pe_legalize.batch_done",
            processed=processed,
            skipped=skipped,
            running_processed=total_processed,
            running_skipped=total_skipped,
        )

    log.info(
        "pe_legalize.done",
        processed=total_processed,
        skipped=total_skipped,
        total=len(laws),
    )
    await close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
