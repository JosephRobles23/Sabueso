"""LLMClient — unified gateway to OpenRouter / Anthropic.

Responsibilities:
- Single entry point `complete(model, messages, tools=None, breakpoints=None)`.
- Exponential backoff retry on 429 / 503.
- Token + USD cost accounting written back into the graph state
  (`state.token_usage`, `state.cost_usd`).
- Auto-fallback to Anthropic SDK when OpenRouter drops cache stats on
  `anthropic/*` models.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .caching import apply_cache_breakpoints, openrouter_respects_cache
from .pricing import estimate_cost
from .routing import RouteResolver, global_resolver

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 503}
DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY = 0.5  # seconds


class TransportError(Exception):
    """Raised by HTTP transports; carries an optional HTTP status code."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _OpenRouterTransport(Protocol):
    async def __call__(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]: ...


class _AnthropicTransport(Protocol):
    async def __call__(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]: ...


@dataclass
class StateAccumulator:
    """Mutable view of the bits of InvestigationState we update.

    BaseInvestigator passes the LangGraph state dict in; we mutate keys.
    This indirection keeps client.py independent of TypedDict definitions
    while still writing back to the right place.
    """

    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0

    @classmethod
    def from_state(cls, state: dict[str, Any] | None) -> StateAccumulator:
        if state is None:
            return cls()
        usage = state.setdefault("token_usage", {})
        if not isinstance(usage, dict):
            usage = {}
            state["token_usage"] = usage
        cost = float(state.get("cost_usd") or 0.0)
        acc = cls(token_usage=usage, cost_usd=cost)
        acc._state = state  # type: ignore[attr-defined]
        return acc

    def add(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        self.token_usage["input"] = self.token_usage.get("input", 0) + input_tokens
        self.token_usage["output"] = self.token_usage.get("output", 0) + output_tokens
        if cache_write_tokens:
            self.token_usage["cache_write"] = (
                self.token_usage.get("cache_write", 0) + cache_write_tokens
            )
        if cache_read_tokens:
            self.token_usage["cache_read"] = (
                self.token_usage.get("cache_read", 0) + cache_read_tokens
            )
        per_model = self.token_usage.setdefault("by_model", {})
        if not isinstance(per_model, dict):
            per_model = {}
            self.token_usage["by_model"] = per_model
        bucket = per_model.setdefault(model, {"input": 0, "output": 0})
        bucket["input"] += input_tokens
        bucket["output"] += output_tokens

        delta = estimate_cost(
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
        )
        self.cost_usd = round(self.cost_usd + delta, 8)
        state = getattr(self, "_state", None)
        if state is not None:
            state["cost_usd"] = self.cost_usd
        return delta


@dataclass
class LLMResponse:
    text: str
    raw: dict[str, Any]
    usage: dict[str, Any]
    model: str
    provider: str
    cost_delta_usd: float
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    """Thin async client over OpenRouter with optional Anthropic fallback.

    Transports are injectable for testing — pass mocks via constructor.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        anthropic_api_key: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        openrouter_transport: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        anthropic_transport: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        resolver: RouteResolver | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = base_url
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._openrouter = openrouter_transport or _default_openrouter_transport(
            self.base_url, self.api_key
        )
        self._anthropic = anthropic_transport or _default_anthropic_transport(
            self.anthropic_api_key
        )
        self._sleep = sleep
        self._resolver = resolver or global_resolver()

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        breakpoints: list[int] | None = None,
        state: dict[str, Any] | None = None,
    ) -> LLMResponse:
        prepared = (
            apply_cache_breakpoints(messages, breakpoints) if breakpoints else messages
        )
        decision = self._resolver.resolve(model, needs_cache=bool(breakpoints))

        if decision.provider == "anthropic":
            transport = self._anthropic
        else:
            transport = self._openrouter

        raw = await self._with_retry(
            transport,
            model=decision.model,
            messages=prepared,
            tools=tools,
        )

        usage = raw.get("usage") or {}
        if decision.provider == "openrouter":
            self._resolver.observe(model, openrouter_respects_cache(usage))

        text, tool_calls = _extract_output(raw)
        acc = StateAccumulator.from_state(state)
        delta = acc.add(
            model=model,
            input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            cache_write_tokens=int(usage.get("cache_creation_input_tokens") or 0),
            cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        )
        return LLMResponse(
            text=text,
            raw=raw,
            usage=usage,
            model=model,
            provider=decision.provider,
            cost_delta_usd=delta,
            tool_calls=tool_calls,
        )

    async def _with_retry(
        self,
        transport: Callable[..., Awaitable[dict[str, Any]]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                return await transport(**kwargs)
            except TransportError as exc:
                attempt += 1
                if (
                    exc.status_code not in RETRYABLE_STATUS
                    or attempt > self.max_retries
                ):
                    raise
                delay = self.base_delay * (2 ** (attempt - 1))
                # decorrelated jitter
                delay = random.uniform(self.base_delay, delay * 1.5)
                log.warning(
                    "LLM transport %s on attempt %d, sleeping %.2fs",
                    exc.status_code,
                    attempt,
                    delay,
                )
                await self._sleep(delay)


def _extract_output(raw: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Pull `text` + `tool_calls` out of either OpenAI-style or Anthropic-style payloads."""
    # OpenAI / OpenRouter shape: choices[0].message.{content, tool_calls}
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        text = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        return text, list(calls)

    # Anthropic shape: content = list of {type, text} | {type:"tool_use", ...}
    content = raw.get("content")
    if isinstance(content, list):
        text_parts: list[str] = []
        calls: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(block)
        return "".join(text_parts), calls

    return "", []


def _default_openrouter_transport(
    base_url: str, api_key: str
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Lazy-import httpx so tests don't pay for it."""

    async def call(
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        import httpx  # noqa: PLC0415

        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://sabueso.app",
            "X-Title": "Sabueso",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        if r.status_code >= 400:
            raise TransportError(
                f"OpenRouter {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )
        return r.json()

    return call


def _default_anthropic_transport(
    api_key: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def call(
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            from anthropic import AsyncAnthropic  # noqa: PLC0415
        except ImportError as exc:
            raise TransportError(
                "anthropic SDK not installed; cannot fallback"
            ) from exc

        sys_blocks: list[dict[str, Any]] = []
        user_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content")
                if isinstance(content, str):
                    sys_blocks.append({"type": "text", "text": content})
                elif isinstance(content, list):
                    sys_blocks.extend(content)
            else:
                user_msgs.append(m)

        client = AsyncAnthropic(api_key=api_key)
        try:
            resp = await client.messages.create(
                model=model,
                system=sys_blocks or None,
                messages=user_msgs,
                tools=tools or [],
                max_tokens=4096,
            )
        except Exception as exc:  # network / API errors
            status = getattr(exc, "status_code", None)
            raise TransportError(str(exc), status_code=status) from exc
        return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    return call
