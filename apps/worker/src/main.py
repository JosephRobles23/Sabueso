"""Worker entrypoint — corre 1 investigación end-to-end (S-10).

Lee ``INVESTIGATION_ID`` del entorno, abre el pool a Supabase Postgres,
abre un ``PostgresSaver`` para checkpointing de LangGraph, construye
``GraphDeps`` con El Contador como único runner real, compila el grafo y
lo invoca con ``thread_id=investigation_id``. Exit code 0 si la
investigación termina ``complete``, 1 si falla.

El logging es structlog JSON: cada evento del worker se vuelca a stdout
en formato consumible por Cloud Logging. Las claves canónicas son
``event``, ``investigation_id``, ``status``, ``cost_usd`` y, en errores,
``error``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import structlog

from .investigators.contador import ElContador
from .llm.client import LLMClient
from .orchestrator import (
    GraphDeps,
    build_graph,
    open_postgres_checkpointer,
)
from .tools.registry import load_pe_tools

DEFAULT_COUNTRY = "pe"
DEFAULT_LOCALE = "es"


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    )


async def _fetch_investigation_row(
    pool: asyncpg.Pool,
    investigation_id: str,
) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        """
        SELECT id, target_entity_id, country, locale, status, user_id
        FROM investigations
        WHERE id = $1
        """,
        investigation_id,
    )
    return dict(row) if row else None


async def _mark_failed(
    pool: asyncpg.Pool,
    investigation_id: str,
    error: str,
) -> None:
    try:
        await pool.execute(
            """
            UPDATE investigations
            SET status = 'failed', finished_at = now()
            WHERE id = $1
            """,
            investigation_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging path
        structlog.get_logger("sabueso.worker").error(
            "worker.mark_failed_error",
            investigation_id=investigation_id,
            error=str(exc),
            original_error=error,
        )


async def run_async() -> int:
    log = structlog.get_logger("sabueso.worker")

    investigation_id = os.environ.get("INVESTIGATION_ID")
    if not investigation_id:
        log.error("worker.missing_investigation_id")
        return 2

    structlog.contextvars.bind_contextvars(investigation_id=investigation_id)

    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        log.error("worker.missing_db_url")
        return 2

    log.info(
        "worker.started",
        task_attempt=os.environ.get("CLOUD_RUN_TASK_ATTEMPT"),
        task_index=os.environ.get("CLOUD_RUN_TASK_INDEX"),
        execution=os.environ.get("CLOUD_RUN_EXECUTION"),
    )

    # Carga las tools de Perú para que el ToolRegistry las tenga
    # registradas antes de instanciar El Contador.
    load_pe_tools()

    pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=1,
        max_size=int(os.environ.get("WORKER_DB_POOL_SIZE", "4")),
        command_timeout=float(os.environ.get("WORKER_DB_TIMEOUT_S", "30")),
    )
    if pool is None:
        log.error("worker.pool_init_failed")
        return 2

    try:
        row = await _fetch_investigation_row(pool, investigation_id)
        if row is None:
            log.error("worker.investigation_not_found")
            return 2

        target_entity_id = str(row["target_entity_id"])
        country = row.get("country") or DEFAULT_COUNTRY
        locale = row.get("locale") or DEFAULT_LOCALE

        llm = LLMClient()
        contador = ElContador(country=country, locale=locale, llm=llm)

        deps = GraphDeps(
            llm=llm,
            db_pool=pool,
            investigator_runners={"contador": contador.run},
            jueza_runner=None,
            persist_dry_run=False,
        )

        with open_postgres_checkpointer(db_url) as checkpointer:
            graph = build_graph(deps, checkpointer=checkpointer)

            initial_state: dict[str, Any] = {
                "investigation_id": investigation_id,
                "target_entity_id": target_entity_id,
                "country": country,
                "locale": locale,
                "user_query": "",
                "plan": [],
                "claims": [],
                "edges": [],
                "events": [],
                "verified_claims": [],
                "dossier_md": "",
                "token_usage": {},
                "cost_usd": 0.0,
                "status": "pending",
            }

            config: dict[str, Any] = {"configurable": {"thread_id": investigation_id}}
            final_state = await graph.ainvoke(initial_state, config=config)  # type: ignore[call-overload]

        status = final_state.get("status", "unknown")
        cost = float(final_state.get("cost_usd") or 0.0)
        claims = final_state.get("claims") or []
        log.info(
            "worker.finished",
            status=status,
            cost_usd=cost,
            claims=len(claims),
        )
        return 0 if status == "complete" else 1

    except Exception as exc:
        log.exception("worker.unhandled_error", error=str(exc))
        await _mark_failed(pool, investigation_id, str(exc))
        return 1
    finally:
        await pool.close()


def run() -> int:
    _configure_logging()
    return asyncio.run(run_async())


if __name__ == "__main__":
    sys.exit(run())
