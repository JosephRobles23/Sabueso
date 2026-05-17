import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import pytest

from src.investigators.base import (
    BaseInvestigator,
    EventEmitter,
    JSONParseError,
    Strategy,
    parse_tolerant_json,
)
from src.llm.client import LLMClient, LLMResponse
from src.llm.routing import RouteResolver
from src.tools.registry import ToolDef, ToolRegistry

# ----------------------------------------------------------- helpers / fakes


@dataclass
class _Queued:
    text: str
    delay: float = 0.0


class FakeLLM:
    """Drop-in for LLMClient — returns queued .text on each .complete call."""

    def __init__(self) -> None:
        self.queue: list[_Queued] = []
        self.calls: list[dict[str, Any]] = []

    def push(self, text: str, *, delay: float = 0.0) -> None:
        self.queue.append(_Queued(text=text, delay=delay))

    async def complete(self, **kwargs: Any) -> LLMResponse:
        if not self.queue:
            raise AssertionError("FakeLLM: no queued responses")
        item = self.queue.pop(0)
        self.calls.append(kwargs)
        if item.delay:
            await asyncio.sleep(item.delay)
        return LLMResponse(
            text=item.text,
            raw={},
            usage={},
            model=kwargs.get("model", "fake"),
            provider="fake",
            cost_delta_usd=0.0,
        )


class RecordingEmitter(EventEmitter):
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


def _register_tool(name: str, country: str, handler):
    ToolRegistry.register_tool(
        ToolDef(name=name, country=country, handler=handler)
    )


# ----------------------------------------------------------- concrete fixtures


class ReWOOSubagent(BaseInvestigator):
    callsign = "rewoo_test"
    role = "test"
    color = "violet-500"
    model = "moonshot/kimi-k2.6"
    strategy = Strategy.REWOO
    allowed_tools = ["tool_a", "tool_b", "tool_c"]
    system_prompt_path = "contador"

    async def _plan_prompt(self, task, state):
        return [{"role": "user", "content": "plan"}]

    async def _react_decide_prompt(self, task, history, state):
        return [{"role": "user", "content": "decide"}]

    def _claims_from_results(self, task, results, synthesis):
        # one claim per tool result, plus surface errors
        return [
            {"tool": r["tool"], "ok": "result" in r, "data": r.get("result")}
            for r in results
        ]


class ReActSubagent(BaseInvestigator):
    callsign = "react_test"
    role = "test"
    color = "rose-500"
    model = "deepseek/deepseek-v4-flash"
    strategy = Strategy.REACT
    allowed_tools = ["tool_a"]
    system_prompt_path = "detective"

    async def _plan_prompt(self, task, state):
        return [{"role": "user", "content": "plan"}]

    async def _react_decide_prompt(self, task, history, state):
        return [{"role": "user", "content": "decide"}]

    def _claims_from_results(self, task, history, synthesis):
        return [
            {"thought": s.thought, "action": s.action, "obs": s.observation}
            for s in history
            if s.action != "finish"
        ]


# -------------------------------------------------------------------- tests


def test_baseinvestigator_is_abstract():
    with pytest.raises(TypeError):
        BaseInvestigator()  # type: ignore[abstract]


def test_strategy_enum_members():
    assert Strategy.REWOO.value == "rewoo"
    assert Strategy.REACT.value == "react"
    assert len(Strategy) == 2


def test_subclass_missing_attrs_fails():
    class Broken(BaseInvestigator):
        # intentionally missing class attributes
        async def _plan_prompt(self, task, state):
            return []

        async def _react_decide_prompt(self, task, history, state):
            return []

        def _claims_from_results(self, task, results, synthesis):
            return []

    llm = FakeLLM()
    with pytest.raises(TypeError):
        Broken(country="pe", llm=llm)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rewoo_runs_three_tools_in_parallel():
    started: list[str] = []
    finished: list[str] = []
    barrier = asyncio.Event()

    async def make_tool(name):
        async def handler(**_):
            started.append(name)
            # wait until all 3 have started, proving parallelism
            if len(started) == 3:
                barrier.set()
            await barrier.wait()
            finished.append(name)
            return {"name": name}

        return handler

    for t in ("tool_a", "tool_b", "tool_c"):
        _register_tool(t, "pe", await make_tool(t))

    llm = FakeLLM()
    llm.push(
        json.dumps(
            {
                "steps": [
                    {"tool": "tool_a", "args": {}},
                    {"tool": "tool_b", "args": {}},
                    {"tool": "tool_c", "args": {}},
                ]
            }
        )
    )

    agent = ReWOOSubagent(country="pe", llm=llm)  # type: ignore[arg-type]
    state: dict = {"investigation_id": "inv-1"}
    claims = await agent.run({"task": "do it"}, state)

    assert len(claims) == 3
    assert all(c["ok"] for c in claims)
    assert set(finished) == {"tool_a", "tool_b", "tool_c"}


@pytest.mark.asyncio
async def test_rewoo_permission_gate():
    async def forbidden(**_):
        return "should not run"

    _register_tool("tool_a", "pe", forbidden)
    _register_tool("forbidden_tool", "pe", forbidden)

    llm = FakeLLM()
    llm.push(json.dumps({"steps": [{"tool": "forbidden_tool", "args": {}}]}))

    agent = ReWOOSubagent(country="pe", llm=llm)  # type: ignore[arg-type]
    state: dict = {"investigation_id": "inv-1"}
    claims = await agent.run({"task": "x"}, state)
    # permission denied is captured as error claim, not raised
    assert claims[0]["ok"] is False


@pytest.mark.asyncio
async def test_rewoo_synthesize_hook():
    async def handler(**_):
        return "data"

    _register_tool("tool_a", "pe", handler)

    class WithSynth(ReWOOSubagent):
        async def _synthesize_prompt(self, task, plan, results, state):
            return [{"role": "user", "content": "synthesize"}]

    llm = FakeLLM()
    llm.push(json.dumps({"steps": [{"tool": "tool_a", "args": {}}]}))
    llm.push("synthesis-text")

    agent = WithSynth(country="pe", llm=llm)  # type: ignore[arg-type]
    await agent.run({"task": "x"}, {"investigation_id": "i"})
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_react_three_iterations():
    observations: list[int] = []

    async def handler(step: int = 0, **_):
        observations.append(step)
        return {"step": step}

    _register_tool("tool_a", "pe", handler)

    llm = FakeLLM()
    llm.push(json.dumps({"thought": "look", "action": "tool_a", "args": {"step": 1}}))
    llm.push(json.dumps({"thought": "more", "action": "tool_a", "args": {"step": 2}}))
    llm.push(json.dumps({"thought": "last", "action": "tool_a", "args": {"step": 3}}))
    llm.push(json.dumps({"thought": "done", "action": "finish", "args": {}}))

    agent = ReActSubagent(country="pe", llm=llm)  # type: ignore[arg-type]
    claims = await agent.run({"task": "loop"}, {"investigation_id": "i"})
    assert observations == [1, 2, 3]
    assert len(claims) == 3  # finish step filtered out by _claims_from_results


@pytest.mark.asyncio
async def test_react_max_steps_cap():
    async def handler(**_):
        return "ok"

    _register_tool("tool_a", "pe", handler)

    llm = FakeLLM()
    # never finishes
    for _ in range(20):
        llm.push(json.dumps({"thought": "loop", "action": "tool_a", "args": {}}))

    agent = ReActSubagent(  # type: ignore[arg-type]
        country="pe",
        llm=llm,
        max_react_steps=4,
    )
    claims = await agent.run({"task": "x"}, {"investigation_id": "i"})
    assert len(claims) == 4


@pytest.mark.asyncio
async def test_react_hard_timeout():
    called = {"n": 0}

    async def slow(**_):
        called["n"] += 1
        await asyncio.sleep(0.5)
        return "ok"

    _register_tool("tool_a", "pe", slow)

    llm = FakeLLM()
    for _ in range(20):
        llm.push(json.dumps({"thought": "go", "action": "tool_a", "args": {}}))

    agent = ReActSubagent(  # type: ignore[arg-type]
        country="pe",
        llm=llm,
        max_react_steps=15,
        hard_timeout_s=0.3,
    )
    start = time.monotonic()
    await agent.run({"task": "x"}, {"investigation_id": "i"})
    elapsed = time.monotonic() - start
    # gives up before completing all 15 steps
    assert elapsed < 2.0
    assert called["n"] < 15


@pytest.mark.asyncio
async def test_react_json_retry_on_malformed():
    async def handler(**_):
        return "ok"

    _register_tool("tool_a", "pe", handler)

    llm = FakeLLM()
    # first malformed, second valid
    llm.push("totally not json")
    llm.push(json.dumps({"thought": "x", "action": "finish", "args": {}}))

    agent = ReActSubagent(country="pe", llm=llm)  # type: ignore[arg-type]
    claims = await agent.run({"task": "x"}, {"investigation_id": "i"})
    assert claims == []  # only finish step, filtered out
    assert len(llm.calls) == 2  # retry happened


@pytest.mark.asyncio
async def test_emit_event_appends_to_state_events():
    async def handler(**_):
        return "x"

    _register_tool("tool_a", "pe", handler)

    llm = FakeLLM()
    llm.push(json.dumps({"steps": [{"tool": "tool_a", "args": {}}]}))

    emitter = RecordingEmitter()
    agent = ReWOOSubagent(country="pe", llm=llm, emitter=emitter)  # type: ignore[arg-type]
    state: dict = {"investigation_id": "inv-7"}
    await agent.run({"task": "x"}, state)

    types = [e["type"] for e in emitter.events]
    assert "agent_started" in types
    assert "agent_finished" in types
    assert all(e["agent"] == "rewoo_test" for e in emitter.events)
    # state.events also populated
    assert len(state["events"]) == len(emitter.events)


@pytest.mark.asyncio
async def test_tool_not_registered_for_country():
    # tool_a only registered for cl
    async def handler(**_):
        return "x"

    _register_tool("tool_a", "cl", handler)

    llm = FakeLLM()
    llm.push(json.dumps({"steps": [{"tool": "tool_a", "args": {}}]}))
    agent = ReWOOSubagent(country="pe", llm=llm)  # type: ignore[arg-type]
    claims = await agent.run({"task": "x"}, {"investigation_id": "i"})
    assert claims[0]["ok"] is False


@pytest.mark.asyncio
async def test_load_system_prompt_uses_loader():
    llm = FakeLLM()
    agent = ReWOOSubagent(country="pe", llm=llm, locale="es")  # type: ignore[arg-type]
    loaded = agent.load_system_prompt()
    assert loaded.callsign == "contador"
    assert "El Contador" in loaded.body


# -------------------------------------------------- tolerant JSON parsing


def test_parse_fenced_json():
    text = 'noise\n```json\n{"a": 1}\n```\nmore'
    assert parse_tolerant_json(text) == {"a": 1}


def test_parse_unfenced_json():
    text = 'pre {"a": 2} post'
    assert parse_tolerant_json(text) == {"a": 2}


def test_parse_plain_json():
    assert parse_tolerant_json('{"a": 3}') == {"a": 3}


def test_parse_array():
    text = "noise [1, 2, 3] noise"
    assert parse_tolerant_json(text) == [1, 2, 3]


def test_parse_handles_strings_with_braces():
    text = 'before {"msg": "this has } in it"} after'
    assert parse_tolerant_json(text) == {"msg": "this has } in it"}


def test_parse_empty_raises():
    with pytest.raises(JSONParseError):
        parse_tolerant_json("")


def test_parse_garbage_raises():
    with pytest.raises(JSONParseError):
        parse_tolerant_json("this has no json anywhere here")


# -------------------------------------------------- integration with real LLMClient


@pytest.mark.asyncio
async def test_real_llmclient_tracks_cost_through_base():
    """End-to-end: BaseInvestigator + real LLMClient + fake transport."""

    async def handler(**_):
        return "x"

    _register_tool("tool_a", "pe", handler)

    async def fake_transport(**kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"steps": [{"tool": "tool_a", "args": {}}]}
                        ),
                        "tool_calls": [],
                    }
                }
            ],
            "usage": {"prompt_tokens": 200, "completion_tokens": 80},
        }

    async def _noop_sleep(_: float) -> None:
        return None

    client = LLMClient(
        openrouter_transport=fake_transport,
        sleep=_noop_sleep,
        resolver=RouteResolver(),
    )
    agent = ReWOOSubagent(country="pe", llm=client)
    state: dict = {"investigation_id": "i"}
    await agent.run({"task": "x"}, state)
    assert state["token_usage"]["input"] == 200
    assert state["cost_usd"] > 0
