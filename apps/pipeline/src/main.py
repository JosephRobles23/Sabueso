"""CLI entrypoint del Cloud Run Job pipeline-ingest.

Uso (local):
  python -m src.main --flow pe_legalize
  python -m src.main --flow pe_seace
  python -m src.main --flow pe_jne_pdfs
  python -m src.main --flow all

En Cloud Run Jobs el flow se selecciona via env var PIPELINE_FLOW.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from flows import pe_jne_pdfs_flow, pe_legalize_flow, pe_seace_flow
from flows.common.db import close_pool
from flows.common.logging import configure as configure_logging
from flows.common.logging import get_logger

FLOWS = {
    "pe_legalize": pe_legalize_flow.run,
    "pe_seace": pe_seace_flow.run,
    "pe_jne_pdfs": pe_jne_pdfs_flow.run,
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sabueso ingest pipeline")
    p.add_argument(
        "--flow",
        choices=[*FLOWS.keys(), "all"],
        default=os.environ.get("PIPELINE_FLOW", "all"),
        help="Flow a correr (default: PIPELINE_FLOW env o 'all')",
    )
    return p.parse_args()


async def _run_all() -> int:
    log = get_logger("sabueso.pipeline.main")
    rc = 0
    for name, runner in FLOWS.items():
        log.info("pipeline.flow_start", flow=name)
        try:
            result = await runner()
            log.info("pipeline.flow_done", flow=name, exit_code=result)
            if result != 0:
                rc = result
        except Exception as e:
            log.exception("pipeline.flow_crashed", flow=name, error=str(e))
            rc = 1
    return rc


async def _amain() -> int:
    args = _parse_args()
    configure_logging()
    try:
        if args.flow == "all":
            return await _run_all()
        return await FLOWS[args.flow]()
    finally:
        await close_pool()


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
