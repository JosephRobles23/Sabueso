"""Route LLM calls between OpenRouter and direct Anthropic SDK.

OpenRouter unifies billing but does not always forward Anthropic prompt
caching. Strategy: try OpenRouter first; if a model is `anthropic/*` AND we
have detected (via a prior probe) that OpenRouter is dropping cache stats,
fall back to Anthropic SDK directly.

Detection is sticky: once we observe cache stats on an Anthropic call via
OpenRouter, we trust the route. If we never see them on an `anthropic/*`
call, we mark OpenRouter as cache-broken for that session.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RouteDecision:
    provider: str  # "openrouter" | "anthropic"
    model: str  # provider-specific model id


class RouteResolver:
    """Per-process state tracking which provider to use for Anthropic models."""

    def __init__(self) -> None:
        self._openrouter_cache_ok: bool | None = None

    def observe(self, model: str, cache_stats_present: bool) -> None:
        """Record whether the last OpenRouter response for an anthropic/* model
        included cache stats. Sticky in either direction once observed."""
        if not model.startswith("anthropic/"):
            return
        if cache_stats_present:
            self._openrouter_cache_ok = True
        elif self._openrouter_cache_ok is None:
            # only mark broken if we haven't already proven it works
            self._openrouter_cache_ok = False

    def resolve(self, model: str, *, needs_cache: bool) -> RouteDecision:
        if model.startswith("anthropic/") and needs_cache and self._openrouter_cache_ok is False:
            # strip provider prefix for direct Anthropic SDK
            anthropic_model = model.split("/", 1)[1]
            return RouteDecision(provider="anthropic", model=anthropic_model)
        return RouteDecision(provider="openrouter", model=model)

    @property
    def openrouter_cache_ok(self) -> bool | None:
        return self._openrouter_cache_ok


_GLOBAL = RouteResolver()


def global_resolver() -> RouteResolver:
    return _GLOBAL
