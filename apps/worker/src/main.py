"""Placeholder entrypoint for the Sabueso investigation worker.

S-07 ships this image to validate the Cloud Run Jobs deployment path (build,
push, IAM, env-var override, exit-code propagation). S-06 replaces the body of
``run()`` with the LangGraph orchestrator — the surrounding Dockerfile,
job manifest and dispatch wiring stay the same.
"""

from __future__ import annotations

import os
import sys

import structlog

from src.observability import configure_langsmith, configure_logging


def run() -> int:
    configure_logging()
    configure_langsmith()
    log = structlog.get_logger("sabueso.worker")
    log.info(
        "worker.placeholder_started",
        investigation_id=os.environ.get("INVESTIGATION_ID"),
        task_attempt=os.environ.get("CLOUD_RUN_TASK_ATTEMPT"),
        task_index=os.environ.get("CLOUD_RUN_TASK_INDEX"),
        execution=os.environ.get("CLOUD_RUN_EXECUTION"),
    )
    log.info("worker.placeholder_done")
    return 0


if __name__ == "__main__":
    sys.exit(run())
