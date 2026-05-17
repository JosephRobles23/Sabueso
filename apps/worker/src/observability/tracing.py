"""LangSmith tracing wrappers for the orchestrator.

The hackathon needs every investigation to show up as a single trace in
LangSmith with one root span per investigation_id and a child span per node.
That is what ``@traceable`` from ``langsmith`` does — but importing it
unconditionally couples test runs to LANGCHAIN_API_KEY, and the S-06 graph is
still in flux. So we expose a thin wrapper:

* ``traceable(...)`` — drop-in replacement for ``langsmith.traceable``. Falls
  back to an identity decorator when LangSmith is disabled (no env var, no
  package, or import failure), so existing code keeps working in CI / unit
  tests without a key.

* ``configure_langsmith()`` — call once at worker boot. Logs the resolved
  project / endpoint so a misconfigured key shows up as a structured event,
  not a silent no-op.

S-06 will sprinkle ``@traceable`` on the individual node closures
(``sabueso_plan``, ``collect_claims``, etc.) once those signatures settle.
This module is the import target so the refactor is one-line per node.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

log = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _langsmith_enabled() -> bool:
    if not os.environ.get("LANGCHAIN_API_KEY"):
        return False
    flag = os.environ.get("LANGCHAIN_TRACING_V2", "").lower()
    return flag in {"1", "true", "yes"}


def _identity_decorator(*_dargs: Any, **_dkwargs: Any) -> Callable[[F], F]:
    """Decorator that returns the function unchanged."""

    def _wrap(fn: F) -> F:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return inner  # type: ignore[return-value]

    return _wrap


def _resolve_traceable() -> Callable[..., Any]:
    """Lazily import langsmith.traceable; fall back to identity on failure."""
    if not _langsmith_enabled():
        return _identity_decorator
    try:
        from langsmith import traceable as _real_traceable
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("tracing.langsmith_import_failed", error=str(exc))
        return _identity_decorator
    return _real_traceable


# Resolve once at import time — re-evaluating per-call would dominate runtime.
# Tests that need to flip the flag should call ``reload_tracing()``.
traceable: Callable[..., Any] = _resolve_traceable()


def reload_tracing() -> None:
    """Re-evaluate the env vars and rebind ``traceable``. Test-only."""
    global traceable
    traceable = _resolve_traceable()


def configure_langsmith() -> None:
    """Log the active LangSmith config; safe to call when disabled."""
    if not _langsmith_enabled():
        log.info("tracing.langsmith_disabled")
        return
    log.info(
        "tracing.langsmith_enabled",
        project=os.environ.get("LANGCHAIN_PROJECT", "default"),
        endpoint=os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    )


__all__ = ["configure_langsmith", "reload_tracing", "traceable"]
