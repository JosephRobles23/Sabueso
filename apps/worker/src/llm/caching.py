"""Anthropic prompt-caching helpers.

Anthropic allows up to 4 `cache_control: {type: "ephemeral"}` breakpoints
per request. Breakpoints mark a position; everything *before and including*
the marker is cacheable. Sabueso uses the convention of 4 breakpoints:
1. identity / global rules
2. team roster / capabilities
3. tool catalog
4. few-shot examples
(Variable target context is left uncached.)

apply_cache_breakpoints mutates messages in-place AND returns them so the
call site reads naturally.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MAX_BREAKPOINTS = 4


class CacheBreakpointError(ValueError):
    pass


def apply_cache_breakpoints(
    messages: list[dict[str, Any]],
    breakpoints: list[int],
) -> list[dict[str, Any]]:
    """Inject `cache_control: ephemeral` markers at the given message indices.

    For each index, the message's content is normalized to the Anthropic
    structured form (list of content blocks) and a `cache_control` field is
    set on the *last* block of that message.

    Args:
        messages: list of {"role": str, "content": str | list[dict]} dicts.
        breakpoints: message indices where the cache should end.

    Raises:
        CacheBreakpointError: if more than 4 breakpoints are requested or
            any index is out of range.
    """
    if len(breakpoints) > MAX_BREAKPOINTS:
        raise CacheBreakpointError(
            f"Anthropic allows at most {MAX_BREAKPOINTS} breakpoints, "
            f"got {len(breakpoints)}"
        )

    out = deepcopy(messages)
    for idx in breakpoints:
        if idx < 0 or idx >= len(out):
            raise CacheBreakpointError(
                f"breakpoint {idx} out of range for {len(out)} messages"
            )
        msg = out[idx]
        content = msg.get("content")
        if isinstance(content, str):
            blocks: list[dict[str, Any]] = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            blocks = [dict(b) for b in content]
        else:
            raise CacheBreakpointError(
                f"message {idx} has unsupported content type {type(content)}"
            )
        if not blocks:
            raise CacheBreakpointError(f"message {idx} has empty content")
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
        msg["content"] = blocks
        out[idx] = msg
    return out


def count_cache_markers(messages: list[dict[str, Any]]) -> int:
    """Count how many ephemeral cache_control markers are present.

    Useful in tests to verify breakpoint injection.
    """
    n = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("cache_control"):
                    n += 1
    return n


def openrouter_respects_cache(response_usage: dict[str, Any] | None) -> bool:
    """Heuristic: did OpenRouter forward Anthropic cache stats?

    OpenRouter relays Anthropic's response usage when the upstream provider
    is Anthropic. If `cache_creation_input_tokens` or
    `cache_read_input_tokens` appear in usage, caching is being honored.
    """
    if not response_usage:
        return False
    return any(
        response_usage.get(k) is not None
        for k in ("cache_creation_input_tokens", "cache_read_input_tokens")
    )
