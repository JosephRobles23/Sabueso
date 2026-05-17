"""Unit tests del ToolRegistry, cache layer, errors y rate limiter."""

from __future__ import annotations

import time

import pytest
from pydantic import BaseModel

from src.tools import (
    InvalidInputError,
    RateLimitedError,
    SourceUnavailableError,
    ToolError,
    ToolRegistry,
)
from src.tools.cache import ToolCache, cached_tool_call
from src.tools.rate_limit import RateLimiter


class _In(BaseModel):
    value: str


class _Out(BaseModel):
    echo: str


def _register_dummy(country: str = "pe", name: str = "dummy_echo") -> int:
    """Registra dinámicamente una tool y devuelve el contador de invocaciones."""
    counter = {"n": 0}

    async def handler(payload: _In) -> _Out:
        counter["n"] += 1
        return _Out(echo=payload.value.upper())

    handler.__name__ = name
    ToolRegistry.register(
        country=country,
        input_model=_In,
        output_model=_Out,
        cache_ttl=60,
    )(handler)
    return counter  # type: ignore[return-value]


def test_register_and_get_by_country(isolated_registry):
    ToolRegistry._reset()
    _register_dummy()
    tool = ToolRegistry.get("pe", "dummy_echo")
    assert tool.country == "pe"
    assert tool.input_model is _In
    assert tool.output_model is _Out
    # filter by allowed list
    tools = ToolRegistry.get_tools_for("pe", ["dummy_echo"])
    assert len(tools) == 1
    assert tools[0].name == "dummy_echo"
    # unknown country returns empty
    assert ToolRegistry.get_tools_for("ar") == []


def test_export_as_mcp_returns_valid_manifest(isolated_registry):
    ToolRegistry._reset()
    _register_dummy()
    manifest = ToolRegistry.export_as_mcp()
    assert "schemaVersion" in manifest
    assert "tools" in manifest
    tool = manifest["tools"][0]
    assert tool["name"] == "dummy_echo"
    assert "inputSchema" in tool
    assert "outputSchema" in tool
    assert tool["inputSchema"]["properties"]["value"]["type"] == "string"
    assert tool["x-sabueso"]["country"] == "pe"
    assert tool["x-sabueso"]["cache_ttl_seconds"] == 60


@pytest.mark.asyncio
async def test_cache_hit_skips_handler(isolated_registry):
    ToolRegistry._reset()
    cache = ToolCache(pool=None)
    counter = _register_dummy()

    out1 = await ToolRegistry.call(
        country="pe", name="dummy_echo", args={"value": "hola"}, cache=cache
    )
    out2 = await ToolRegistry.call(
        country="pe", name="dummy_echo", args={"value": "hola"}, cache=cache
    )
    assert out1.echo == "HOLA"
    assert out2.echo == "HOLA"
    assert counter["n"] == 1  # second call hit cache


@pytest.mark.asyncio
async def test_cache_miss_with_different_args(isolated_registry):
    ToolRegistry._reset()
    cache = ToolCache(pool=None)
    counter = _register_dummy()

    await ToolRegistry.call(
        country="pe", name="dummy_echo", args={"value": "a"}, cache=cache
    )
    await ToolRegistry.call(
        country="pe", name="dummy_echo", args={"value": "b"}, cache=cache
    )
    assert counter["n"] == 2


@pytest.mark.asyncio
async def test_invalid_input_raises(isolated_registry):
    ToolRegistry._reset()
    _register_dummy()
    with pytest.raises(InvalidInputError):
        await ToolRegistry.call(country="pe", name="dummy_echo", args={})


def test_cache_key_deterministic():
    args = {"a": 1, "b": [1, 2, 3], "c": "x"}
    permuted = {"c": "x", "b": [1, 2, 3], "a": 1}
    assert ToolCache.make_key("pe", "t", args) == ToolCache.make_key("pe", "t", permuted)


def test_error_hierarchy():
    assert issubclass(RateLimitedError, ToolError)
    assert issubclass(SourceUnavailableError, ToolError)
    assert issubclass(InvalidInputError, ToolError)
    e = RateLimitedError("slow down", retry_after=5.0, tool="t", country="pe")
    assert e.retry_after == 5.0
    assert "[pe:t] slow down" in str(e)


@pytest.mark.asyncio
async def test_rate_limiter_enforces_rate():
    limiter = RateLimiter(default_rate=4.0, default_capacity=1.0)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire("https://example.com/")
    elapsed = time.monotonic() - start
    # 3 acquires at 4/s with capacity 1 → ~0.5s mínimo
    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_cached_tool_call_serializes_pydantic():
    cache = ToolCache(pool=None)

    class _Output(BaseModel):
        n: int

    calls = {"n": 0}

    async def handler(*, v: int) -> _Output:
        calls["n"] += 1
        return _Output(n=v * 2)

    first = await cached_tool_call(
        country="pe",
        tool_name="x",
        args={"v": 3},
        ttl_seconds=10,
        output_model=_Output,
        handler=handler,
        cache=cache,
    )
    second = await cached_tool_call(
        country="pe",
        tool_name="x",
        args={"v": 3},
        ttl_seconds=10,
        output_model=_Output,
        handler=handler,
        cache=cache,
    )
    assert first.n == 6
    assert second.n == 6
    assert calls["n"] == 1
