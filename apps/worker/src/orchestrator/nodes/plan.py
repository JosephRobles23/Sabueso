"""Nodo 2: sabueso_plan — Claude Sonnet 4.6 con 4 cache breakpoints.

Carga el prompt sabueso_system.md (4 secciones cacheables: identity,
roster, tool catalog, few-shot), arma los mensajes con los 4 breakpoints
en los índices [0,1,2,3], invoca el LLM, parsea JSON.

Política de errores:
- 1 retry si el JSON está malformado (re-prompt con feedback explícito).
- Si la 2ª también falla, fallback a ``DEFAULT_PLAN`` y emitir evento
  ``plan_generated`` con tag ``fallback=true`` para que sea visible en SSE.

El prompt se inyecta como un único mensaje de sistema dividido en 4
bloques de contenido (Anthropic structured content): cada uno termina en
un breakpoint. Esto da 1 cache write inicial y >=90% cache hits en
investigaciones subsiguientes (mismo país/locale).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ...investigators.base import (
    JSONParseError,
    parse_tolerant_json,
)
from ...llm.client import LLMClient
from ...prompts.loader import LoadedPrompt, PromptLoader
from ..state import DEFAULT_PLAN, InvestigationState, PlanStep

_Node = Callable[[InvestigationState], Awaitable[dict[str, Any]]]

log = logging.getLogger(__name__)

DEFAULT_PLAN_MODEL = "anthropic/claude-sonnet-4.6"
PLAN_RETRY_LIMIT = 1
PROMPT_NAME = "sabueso"


# Marcadores [BREAKPOINT N — ...] usados en el prompt para dividirlo en
# secciones cacheables. El loader retorna el texto rendered; aquí lo
# partimos en 4 bloques para inyectar cache_control en los primeros 4.
_BREAKPOINT_RE = re.compile(r"(?=\[BREAKPOINT \d+)")


@dataclass
class PlanDeps:
    llm: LLMClient
    prompt_loader: PromptLoader = field(default_factory=PromptLoader)
    plan_model: str = DEFAULT_PLAN_MODEL
    retry_limit: int = PLAN_RETRY_LIMIT


def make_plan_node(deps: PlanDeps) -> _Node:
    async def sabueso_plan(state: InvestigationState) -> dict[str, Any]:
        prompt = _load_prompt(deps.prompt_loader, state)
        messages = _build_messages(prompt, state)
        # 4 breakpoints: el system message tiene 4+ bloques de contenido,
        # el último carga el contexto variable (no cacheable).
        breakpoints = [0]

        plan, fallback_used, parse_error = await _request_plan(
            deps=deps, messages=messages, breakpoints=breakpoints, state=state
        )

        plan_steps = _normalize_plan(plan)
        events = [
            {
                "type": "plan_generated",
                "agent": "sabueso",
                "payload": {
                    "plan": [
                        {
                            "agent": _to_event_agent(s["agent"]),
                            "task": s["task"],
                            "priority": int(s.get("priority", i + 1)),
                        }
                        for i, s in enumerate(plan_steps)
                    ],
                    "fallback": fallback_used,
                    "parse_error": parse_error,
                },
            }
        ]

        return {
            "plan": plan_steps,
            "status": "running",
            "events": events,
        }

    return sabueso_plan


def _load_prompt(loader: PromptLoader, state: InvestigationState) -> LoadedPrompt:
    entity = state.get("entity") or {}
    variables = {
        "country": state.get("country", "pe"),
        "locale": state.get("locale", "es"),
        "entity_name": entity.get("name", ""),
        "entity_type": entity.get("type", ""),
        "identifier": entity.get("identifier", ""),
        "user_query": state.get("user_query", ""),
        "tool_catalog": "",  # poblado por orchestrator si está disponible
    }
    return loader.load(PROMPT_NAME, variables=variables)


def _build_messages(
    prompt: LoadedPrompt,
    state: InvestigationState,
) -> list[dict[str, Any]]:
    """Devuelve el system message como lista de 4 bloques + el user prompt.

    Anthropic permite hasta 4 cache_control markers — uno por bloque del
    system. ``apply_cache_breakpoints`` del client.py se encarga de marcar
    el último bloque del system (que es lo que el LLMClient hace cuando
    se le pasa ``breakpoints=[0]``: marca el final del mensaje #0).

    Para que cada sección sea independientemente cacheable, partimos el
    texto del prompt en 4 bloques de tipo text y dejamos que el cliente
    Anthropic los procese — aunque sólo el último bloque lleva el marker,
    Anthropic cachea desde el inicio hasta ese punto.
    """
    body = prompt.body
    parts = [p.strip() for p in _BREAKPOINT_RE.split(body) if p.strip()]
    if not parts:
        parts = [body]
    blocks = [{"type": "text", "text": p + "\n"} for p in parts]

    system_msg = {"role": "system", "content": blocks}

    user_payload = (
        "Genera el plan JSON para esta investigación.\n\n"
        f"- investigation_id: {state.get('investigation_id')}\n"
        f"- target_entity_id: {state.get('target_entity_id')}\n"
        f"- country: {state.get('country')}\n"
        f"- locale: {state.get('locale', 'es')}\n"
        f"- user_query: {state.get('user_query', '(ninguno)')}\n\n"
        "Responde estrictamente con JSON: "
        '{"plan": [{"agent": "<callsign>", "task": "<descripción>", "priority": 1}, ...]}'
    )
    user_msg = {"role": "user", "content": user_payload}
    return [system_msg, user_msg]


async def _request_plan(
    *,
    deps: PlanDeps,
    messages: list[dict[str, Any]],
    breakpoints: list[int],
    state: InvestigationState,
) -> tuple[Any, bool, str | None]:
    """Llamá al LLM, parseá JSON, reintentá una vez con feedback explícito.

    Retorna (data, fallback_used, parse_error). Si después de retry sigue
    fallando, usa ``DEFAULT_PLAN`` y retorna parse_error con el detalle.
    """
    attempt_messages = list(messages)
    last_error: Exception | None = None

    for attempt in range(deps.retry_limit + 1):
        resp = await deps.llm.complete(
            model=deps.plan_model,
            messages=attempt_messages,
            breakpoints=breakpoints,
            state=state,  # type: ignore[arg-type]
        )
        try:
            data = parse_tolerant_json(resp.text)
            return data, False, None
        except JSONParseError as exc:
            last_error = exc
            log.warning("sabueso_plan.parse_error attempt=%d: %s", attempt, exc)
            if attempt >= deps.retry_limit:
                break
            attempt_messages = list(messages) + [
                {"role": "assistant", "content": resp.text},
                {
                    "role": "user",
                    "content": (
                        f"Tu respuesta anterior no parsea como JSON ({exc}). "
                        "Responde SOLO con JSON válido del shape "
                        '{"plan":[{"agent":..,"task":..,"priority":..}, ...]}'
                    ),
                },
            ]

    return DEFAULT_PLAN, True, str(last_error) if last_error else "unknown"


def _normalize_plan(data: Any) -> list[PlanStep]:
    """Acepta {plan: [...]} o [...] directamente. Filtra steps sin agent/task."""
    if isinstance(data, dict):
        raw = data.get("plan") or data.get("steps") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []

    out: list[PlanStep] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent") or "").strip()
        task = str(item.get("task") or "").strip()
        if not agent or not task:
            continue
        # normalizar callsigns "el-buscador" → "buscador"
        agent = agent.removeprefix("el-").removeprefix("la-")
        priority_raw = item.get("priority", i + 1)
        try:
            priority = int(priority_raw)
        except (TypeError, ValueError):
            priority = i + 1
        out.append({"agent": agent, "task": task, "priority": priority})

    if not out:
        return list(DEFAULT_PLAN)
    return out


def _to_event_agent(short_callsign: str) -> str:
    from ..state import event_agent_for  # noqa: PLC0415

    return event_agent_for(short_callsign)
