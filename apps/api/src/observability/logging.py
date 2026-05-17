"""Structured JSON logging — Cloud Logging compatible.

Cloud Logging auto-parses JSON on stdout and uses the `severity` and
`time` fields (if present) as the first-class log entry attributes. We rename
`level` → `severity` via `add_log_level` + a small processor.
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
    # Stable fields that make filtering in Cloud Logging cheap.
    event_dict.setdefault("service", "sabueso-api")
    env = os.environ.get("ENVIRONMENT")
    if env:
        event_dict.setdefault("environment", env)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """JSON structured logs to stdout — what Cloud Logging picks up automatically."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
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
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
