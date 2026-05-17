"""BaseInvestigator — abstract subagent runner.

Two execution strategies:

- **ReWOO**: plan once → execute all tool steps in parallel → synthesize claims.
- **ReAct**: iterative thought → action → observation loop, capped at
  MAX_REACT_STEPS and a HARD_TIMEOUT_S wall clock.

Both strategies share:
- Permission gate: a subagent can only call tools in `allowed_tools`.
- Cost / token tracking via LLMClient → StateAccumulator.
- Event emission (agent_started, tool_call, tool_error, finish).
- Tolerant JSON parsing: tries fenced code blocks, balanced brace
  extraction, then retries the LLM with explicit error feedback once.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..llm.client import LLMClient, LLMResponse
from ..prompts.loader import LoadedPrompt, PromptLoader
from ..tools.registry import ToolDef, ToolRegistry

log = logging.getLogger(__name__)

MAX_REACT_STEPS = 15
HARD_TIMEOUT_S = 60.0
JSON_RETRY_LIMIT = 1


class Strategy(StrEnum):
    REWOO = "rewoo"
    REACT = "react"


class ToolPermissionError(RuntimeError):
    pass


class JSONParseError(ValueError):
    pass


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActStep:
    thought: str
    action: str  # tool name OR "finish"
    args: dict[str, Any]
    observation: Any = None
    error: str | None = None


@dataclass
class ReWOOPlan:
    steps: list[ToolCall]


class EventEmitter:
    """Default no-op emitter. Real impl writes to investigation_events table."""

    async def emit(self, event: dict[str, Any]) -> None:  # pragma: no cover - default
        log.debug("event: %s", event)


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def parse_tolerant_json(text: str) -> Any:
    """Pull JSON out of an LLM response with several fallbacks.

    1. Try fenced ```json``` block.
    2. Try balanced-brace extraction.
    3. Try the raw text.
    Raises JSONParseError on total failure.
    """
    if not text or not text.strip():
        raise JSONParseError("empty LLM output")

    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    snippet = _extract_balanced(text)
    if snippet is not None:
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise JSONParseError(f"could not parse JSON: {exc}") from exc


def _extract_balanced(text: str) -> str | None:
    starts = {"{": "}", "[": "]"}
    first: int | None = None
    opener: str | None = None
    for i, ch in enumerate(text):
        if ch in starts:
            first = i
            opener = ch
            break
    if first is None or opener is None:
        return None
    closer = starts[opener]
    depth = 0
    in_str = False
    esc = False
    for i in range(first, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[first : i + 1]
    return None


class BaseInvestigator(ABC):
    """Abstract base — concrete subagents set the class attributes."""

    callsign: str
    role: str
    color: str
    model: str
    strategy: Strategy
    allowed_tools: list[str]
    system_prompt_path: str  # "contador" → loads contador_system.md

    def __init__(
        self,
        *,
        country: str,
        locale: str = "es",
        llm: LLMClient,
        emitter: EventEmitter | None = None,
        registry: type[ToolRegistry] | None = None,
        prompt_loader: PromptLoader | None = None,
        max_react_steps: int = MAX_REACT_STEPS,
        hard_timeout_s: float = HARD_TIMEOUT_S,
    ) -> None:
        self._validate_class_attrs()
        self.country = country
        self.locale = locale
        self.llm = llm
        self.emitter = emitter or EventEmitter()
        self.registry = registry or ToolRegistry
        self.prompts = prompt_loader or PromptLoader()
        self.max_react_steps = max_react_steps
        self.hard_timeout_s = hard_timeout_s
        self.tools: list[ToolDef] = self.registry.get_tools_for(
            country, list(self.allowed_tools)
        )
        self._tools_by_name = {t.name: t for t in self.tools}

    def _validate_class_attrs(self) -> None:
        required = (
            "callsign",
            "role",
            "color",
            "model",
            "strategy",
            "allowed_tools",
            "system_prompt_path",
        )
        missing = [
            a
            for a in required
            if not hasattr(self, a) or getattr(self, a, None) in (None, "")
        ]
        if missing:
            raise TypeError(
                f"{type(self).__name__} missing class attributes: {missing}"
            )
        if not isinstance(self.strategy, Strategy):
            raise TypeError("strategy must be a Strategy enum member")

    # ------------------------------------------------------------------ public

    async def run(self, task: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute the task and return a list of claim dicts."""
        await self._emit_event(state, "agent_started", {"task": task.get("task", "")})
        try:
            if self.strategy == Strategy.REWOO:
                claims = await self._run_rewoo(task, state)
            else:
                claims = await self._run_react(task, state)
        except Exception as exc:
            await self._emit_event(state, "agent_error", {"error": str(exc)})
            raise
        await self._emit_event(state, "agent_finished", {"claims": len(claims)})
        return claims

    @abstractmethod
    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return the messages list used for the planning / decision LLM call."""

    @abstractmethod
    def _claims_from_results(
        self,
        task: dict[str, Any],
        results: list[Any],
        synthesis: LLMResponse | None,
    ) -> list[dict[str, Any]]:
        """Transform tool results (ReWOO) or react history (ReAct) into claims."""

    # ------------------------------------------------------------------ ReWOO

    async def _run_rewoo(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        messages = await self._plan_prompt(task, state)
        plan_resp = await self._llm_json_with_retry(
            messages=messages, state=state, expecting="ReWOO plan"
        )
        plan = _coerce_rewoo_plan(plan_resp)

        # Parallel tool execution with permission gate
        coros = [self._invoke_tool(step, state) for step in plan.steps]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Build observation list (swap exceptions for {error: ...} dicts)
        cleaned: list[Any] = []
        for step, res in zip(plan.steps, results, strict=True):
            if isinstance(res, Exception):
                cleaned.append({"tool": step.tool, "error": str(res)})
                await self._emit_event(
                    state, "tool_error", {"tool": step.tool, "error": str(res)}
                )
            else:
                cleaned.append({"tool": step.tool, "result": res})

        # Optional synthesize step
        synth: LLMResponse | None = None
        synth_messages = await self._synthesize_prompt(task, plan, cleaned, state)
        if synth_messages:
            synth = await self.llm.complete(
                model=self.model, messages=synth_messages, state=state
            )

        return self._claims_from_results(task, cleaned, synth)

    async def _synthesize_prompt(
        self,
        task: dict[str, Any],
        plan: ReWOOPlan,
        results: list[Any],
        state: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        """Override to enable a synthesize LLM call after parallel tools.

        Default: skip synthesis (concrete subagents can do it themselves
        in _claims_from_results).
        """
        return None

    # ------------------------------------------------------------------ ReAct

    async def _run_react(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + self.hard_timeout_s
        history: list[ReActStep] = []
        timed_out = False

        for step_idx in range(self.max_react_steps):
            if time.monotonic() >= deadline:
                timed_out = True
                break

            messages = await self._react_decide_prompt(task, history, state)
            try:
                remaining = max(0.1, deadline - time.monotonic())
                decision_raw = await asyncio.wait_for(
                    self._llm_json_with_retry(
                        messages=messages, state=state, expecting="ReAct decision"
                    ),
                    timeout=remaining,
                )
            except TimeoutError:
                timed_out = True
                break

            decision = _coerce_react_decision(decision_raw)
            step = ReActStep(
                thought=decision.get("thought", ""),
                action=decision["action"],
                args=decision.get("args", {}) or {},
            )

            if step.action == "finish":
                history.append(step)
                break

            try:
                step.observation = await self._invoke_tool(
                    ToolCall(tool=step.action, args=step.args), state
                )
            except Exception as exc:
                step.error = str(exc)
                await self._emit_event(
                    state, "tool_error", {"tool": step.action, "error": str(exc)}
                )
            else:
                await self._emit_event(
                    state,
                    "tool_call",
                    {
                        "tool": step.action,
                        "args": step.args,
                        "observation_summary": str(step.observation)[:200],
                    },
                )
            history.append(step)
        else:
            # max steps without explicit finish
            timed_out = False  # not a timeout, just hit step cap

        if timed_out:
            await self._emit_event(state, "react_timeout", {"steps": len(history)})

        return self._claims_from_results(task, history, None)

    @abstractmethod
    async def _react_decide_prompt(
        self,
        task: dict[str, Any],
        history: list[ReActStep],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build messages for the next thought-action-observation decision."""

    # ------------------------------------------------------------------ helpers

    async def _invoke_tool(
        self, call: ToolCall, state: dict[str, Any]
    ) -> Any:
        if call.tool not in self.allowed_tools:
            raise ToolPermissionError(
                f"{self.callsign} cannot call {call.tool!r}; "
                f"allowed={self.allowed_tools}"
            )
        tool = self._tools_by_name.get(call.tool)
        if tool is None:
            raise ToolPermissionError(
                f"{call.tool!r} not registered for country {self.country!r}"
            )
        result = tool.handler(**call.args)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def _llm_json_with_retry(
        self,
        *,
        messages: list[dict[str, Any]],
        state: dict[str, Any],
        expecting: str,
    ) -> Any:
        """Call the LLM, parse JSON tolerantly, retry once with feedback."""
        attempt_messages = list(messages)
        last_error: Exception | None = None
        for attempt in range(JSON_RETRY_LIMIT + 1):
            resp = await self.llm.complete(
                model=self.model, messages=attempt_messages, state=state
            )
            try:
                return parse_tolerant_json(resp.text)
            except JSONParseError as exc:
                last_error = exc
                if attempt >= JSON_RETRY_LIMIT:
                    break
                attempt_messages = list(messages) + [
                    {"role": "assistant", "content": resp.text},
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response did not parse as JSON "
                            f"({expecting}). Error: {exc}. "
                            f"Reply with strictly valid JSON, nothing else."
                        ),
                    },
                ]
        assert last_error is not None
        raise last_error

    async def _emit_event(
        self,
        state: dict[str, Any],
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "type": event_type,
            "agent": self.callsign,
            "investigation_id": state.get("investigation_id"),
            "payload": payload or {},
        }
        # Append to state.events if the slot exists
        events = state.setdefault("events", [])
        if isinstance(events, list):
            events.append(event)
        await self.emitter.emit(event)

    def load_system_prompt(
        self, variables: dict[str, Any] | None = None
    ) -> LoadedPrompt:
        return self.prompts.load(
            self.system_prompt_path,
            variables={
                "country": self.country,
                "locale": self.locale,
                **(variables or {}),
            },
        )


# ----------------------------------------------------------------------- coerce

def _coerce_rewoo_plan(data: Any) -> ReWOOPlan:
    if isinstance(data, dict) and "steps" in data:
        raw_steps = data["steps"]
    elif isinstance(data, list):
        raw_steps = data
    else:
        raise JSONParseError(f"ReWOO plan must be list or {{steps: ...}}, got {type(data)}")
    steps: list[ToolCall] = []
    for s in raw_steps:
        if not isinstance(s, dict):
            raise JSONParseError(f"ReWOO step must be object, got {s!r}")
        tool = s.get("tool") or s.get("action")
        if not tool:
            raise JSONParseError(f"ReWOO step missing 'tool': {s!r}")
        args = s.get("args") or s.get("arguments") or {}
        if not isinstance(args, dict):
            raise JSONParseError(f"ReWOO step 'args' must be object, got {args!r}")
        steps.append(ToolCall(tool=str(tool), args=args))
    return ReWOOPlan(steps=steps)


def _coerce_react_decision(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise JSONParseError(f"ReAct decision must be object, got {type(data)}")
    if "action" not in data:
        raise JSONParseError("ReAct decision missing 'action'")
    return data
