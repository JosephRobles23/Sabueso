import pytest

from src.llm.client import LLMClient, StateAccumulator, TransportError
from src.llm.routing import RouteResolver


def _openrouter_response(text: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    return {
        "choices": [{"message": {"content": text, "tool_calls": []}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


async def _make_transport(payloads):
    calls = []

    async def transport(**kwargs):
        calls.append(kwargs)
        item = payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return transport, calls


@pytest.mark.asyncio
async def test_complete_tracks_tokens_and_cost():
    transport, calls = await _make_transport([_openrouter_response("hello")])
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        resolver=RouteResolver(),
    )
    state: dict = {}
    resp = await client.complete(
        model="moonshot/kimi-k2.6",
        messages=[{"role": "user", "content": "hi"}],
        state=state,
    )
    assert resp.text == "hello"
    assert resp.provider == "openrouter"
    assert state["token_usage"]["input"] == 100
    assert state["token_usage"]["output"] == 50
    assert state["token_usage"]["by_model"]["moonshot/kimi-k2.6"]["input"] == 100
    assert state["cost_usd"] > 0
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_five_calls_accumulate():
    transport, _ = await _make_transport(
        [_openrouter_response("x", 100, 20) for _ in range(5)]
    )
    client = LLMClient(openrouter_transport=transport, sleep=_noop_sleep,
                      resolver=RouteResolver())
    state: dict = {}
    for _ in range(5):
        await client.complete(
            model="moonshot/kimi-k2.6",
            messages=[{"role": "user", "content": "ping"}],
            state=state,
        )
    assert state["token_usage"]["input"] == 500
    assert state["token_usage"]["output"] == 100
    # 500 in * 0.74 + 100 out * 3.50 per 1M
    assert state["cost_usd"] == pytest.approx(
        (500 * 0.74 + 100 * 3.50) / 1_000_000, rel=1e-6
    )


@pytest.mark.asyncio
async def test_retry_on_429_then_success():
    transport, calls = await _make_transport(
        [
            TransportError("rate limited", status_code=429),
            TransportError("rate limited", status_code=429),
            _openrouter_response("ok"),
        ]
    )
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        base_delay=0.01,
        resolver=RouteResolver(),
    )
    resp = await client.complete(
        model="moonshot/kimi-k2.6",
        messages=[{"role": "user", "content": "hi"}],
        state={},
    )
    assert resp.text == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_retry_on_503():
    transport, calls = await _make_transport(
        [
            TransportError("svc down", status_code=503),
            _openrouter_response("ok"),
        ]
    )
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        base_delay=0.01,
        resolver=RouteResolver(),
    )
    resp = await client.complete(
        model="moonshot/kimi-k2.6",
        messages=[{"role": "user", "content": "hi"}],
        state={},
    )
    assert resp.text == "ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_no_retry_on_4xx_non_retryable():
    transport, calls = await _make_transport(
        [TransportError("bad request", status_code=400)]
    )
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        base_delay=0.01,
        resolver=RouteResolver(),
    )
    with pytest.raises(TransportError):
        await client.complete(
            model="moonshot/kimi-k2.6",
            messages=[{"role": "user", "content": "hi"}],
            state={},
        )
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_exhausted():
    transport, calls = await _make_transport(
        [TransportError("rate limited", status_code=429) for _ in range(10)]
    )
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        base_delay=0.001,
        max_retries=2,
        resolver=RouteResolver(),
    )
    with pytest.raises(TransportError):
        await client.complete(
            model="moonshot/kimi-k2.6",
            messages=[{"role": "user", "content": "hi"}],
            state={},
        )
    # initial + 2 retries = 3
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_anthropic_fallback_when_openrouter_cache_broken():
    resolver = RouteResolver()
    resolver.observe("anthropic/claude-sonnet-4.6", cache_stats_present=False)

    or_transport, or_calls = await _make_transport([_openrouter_response("nope")])
    anthropic_payload = {
        "content": [{"type": "text", "text": "from anthropic"}],
        "usage": {
            "input_tokens": 50,
            "output_tokens": 10,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 0,
        },
    }
    an_transport, an_calls = await _make_transport([anthropic_payload])

    client = LLMClient(
        openrouter_transport=or_transport,
        anthropic_transport=an_transport,
        sleep=_noop_sleep,
        resolver=resolver,
    )
    state: dict = {}
    resp = await client.complete(
        model="anthropic/claude-sonnet-4.6",
        messages=[{"role": "system", "content": "ident"}],
        breakpoints=[0],
        state=state,
    )
    assert resp.provider == "anthropic"
    assert resp.text == "from anthropic"
    assert len(an_calls) == 1
    assert len(or_calls) == 0
    # cache token columns picked up
    assert state["token_usage"]["cache_write"] == 200


@pytest.mark.asyncio
async def test_openrouter_observes_cache_success_and_persists():
    resolver = RouteResolver()
    resp_payload = {
        "choices": [{"message": {"content": "hi", "tool_calls": []}}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "cache_creation_input_tokens": 80,
        },
    }
    transport, _ = await _make_transport([resp_payload])
    client = LLMClient(
        openrouter_transport=transport,
        sleep=_noop_sleep,
        resolver=resolver,
    )
    await client.complete(
        model="anthropic/claude-sonnet-4.6",
        messages=[{"role": "system", "content": "ident"}],
        breakpoints=[0],
        state={},
    )
    assert resolver.openrouter_cache_ok is True


def test_state_accumulator_no_state():
    acc = StateAccumulator.from_state(None)
    acc.add(model="moonshot/kimi-k2.6", input_tokens=1000, output_tokens=500)
    assert acc.token_usage["input"] == 1000


async def _noop_sleep(_: float) -> None:
    return None
