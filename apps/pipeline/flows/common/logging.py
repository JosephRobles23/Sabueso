"""Logging configurado para los flows de ingesta.

Cloud Run Jobs colecta stdout como structured logs si el output es JSON.
"""

from __future__ import annotations

import logging
import os

import structlog


def configure(level: str | None = None) -> None:
    log_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(format="%(message)s", level=getattr(logging, log_level, logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
