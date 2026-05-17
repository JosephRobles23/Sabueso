"""Structured JSON logging for the worker — mirrors apps/api/src/observability/logging.py.

The two services keep their own copy on purpose: they have different shutdown
semantics (FastAPI lifespan vs Cloud Run Job exit) and we don't want to spin up
a shared package just for ~50 lines. If a third service needs the same setup,
promote this to packages/observability-py.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog


def _rename_level_to_severity(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    level = event_dict.pop("level", None)
    if level:
        event_dict["severity"] = level.upper()
    return event_dict


def _inject_runtime_context(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    event_dict.setdefault("service", "sabueso-worker")
    env = os.environ.get("ENVIRONMENT")
    if env:
        event_dict.setdefault("environment", env)
    # Cloud Run Jobs sets these per task — make them grep-friendly.
    for env_key, dict_key in (
        ("CLOUD_RUN_EXECUTION", "execution"),
        ("CLOUD_RUN_TASK_INDEX", "task_index"),
        ("CLOUD_RUN_TASK_ATTEMPT", "task_attempt"),
        ("INVESTIGATION_ID", "investigation_id"),
    ):
        val = os.environ.get(env_key)
        if val:
            event_dict.setdefault(dict_key, val)
    return event_dict


def configure_logging(level: str | None = None) -> None:
    """Configure structlog to emit Cloud Logging-friendly JSON on stdout."""
    resolved = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, resolved, logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _rename_level_to_severity,
            _inject_runtime_context,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="time"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )
