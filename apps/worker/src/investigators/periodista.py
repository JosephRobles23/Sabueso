"""El Periodista — archivista de prensa (S-11).

Strategy: ReAct. Empieza amplio (search_news_archive), luego decide
qué archivar (wayback_machine) y si profundiza en redes sociales
(search_twitter_archive).

``_claims_from_results`` consume el history y emite 3 predicates:
``mentioned_in_press`` (1 por artículo), ``archived_at`` (1 por
snapshot Wayback), ``social_post`` (1 por post Twitter).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ..llm.client import LLMResponse
from ..tools.registry import ToolDef
from .base import BaseInvestigator, ReActStep, Strategy

log = logging.getLogger(__name__)

# Prioridad de fuente: 1 = investigación independiente,
# 2 = medios masivos, 3 = web archive.
_PRIORITY_CONFIDENCE = {1: 0.85, 2: 0.65, 3: 0.55}


def _tool_catalog_lines(tools: list[ToolDef[Any, Any]]) -> str:
    if not tools:
        return "(sin tools registradas para este país)"
    lines = []
    for t in tools:
        schema = t.input_schema or {}
        props = list((schema.get("properties") or {}).keys())
        args = ", ".join(props) if props else "(sin args)"
        first_doc = (t.description or "").splitlines()[0].strip()
        lines.append(f"- `{t.name}({args})` — {first_doc}")
    return "\n".join(lines)


def _summarize_history(history: list[ReActStep]) -> str:
    if not history:
        return "(sin observaciones aún)"
    lines = []
    for i, s in enumerate(history, 1):
        if s.action == "finish":
            continue
        obs_str = str(s.observation)[:200] if s.observation is not None else ""
        err_str = f" ERROR={s.error}" if s.error else ""
        lines.append(
            f"{i}. thought={s.thought[:80]!r} action={s.action} args={s.args} "
            f"obs={obs_str}{err_str}"
        )
    return "\n".join(lines) or "(history vacío)"


class ElPeriodista(BaseInvestigator):
    """Archivista de prensa (Perú: news + Wayback + Twitter archive)."""

    callsign = "el-periodista"
    role = "news"
    color = "orange-500"
    model = "anthropic/claude-sonnet-4.6"
    strategy = Strategy.REACT
    allowed_tools = ["search_news_archive", "wayback_machine", "search_twitter_archive"]
    system_prompt_path = "periodista"

    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("ElPeriodista uses ReAct, not ReWOO")

    async def _react_decide_prompt(
        self,
        task: dict[str, Any],
        history: list[ReActStep],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        entity = state.get("entity") or {}
        entity_identifier = (
            task.get("entity_identifier")
            or entity.get("identifier")
            or ""
        )
        entity_name = task.get("entity_name") or entity.get("name") or ""

        loaded = self.load_system_prompt(
            variables={
                "task": task.get("task", ""),
                "entity_identifier": entity_identifier,
                "entity_name": entity_name,
                "tool_catalog": _tool_catalog_lines(self.tools),
            }
        )
        system_msg = {"role": "system", "content": loaded.body}
        user_msg = {
            "role": "user",
            "content": (
                "Pista del orquestador:\n"
                f"- task: {task.get('task', '(sin tarea explícita)')}\n"
                f"- entity_name: {entity_name or '(no provisto)'}\n"
                f"- entity_identifier: {entity_identifier or '(no provisto)'}\n\n"
                "Historial hasta ahora:\n"
                f"{_summarize_history(history)}\n\n"
                "Decidí el próximo step. Formato JSON estricto:\n"
                '{"thought":"...", "action":"<tool|finish>", "args":{...}}\n'
                "Tools permitidas: search_news_archive, wayback_machine, search_twitter_archive.\n"
                "`action=\"finish\"` cuando tengas ≥3 menciones o los lookups "
                "ya no aporten nuevo material."
            ),
        }
        return [system_msg, user_msg]

    def _claims_from_results(
        self,
        task: dict[str, Any],
        results: list[Any],  # ReActStep list
        synthesis: LLMResponse | None,
    ) -> list[dict[str, Any]]:
        history: list[ReActStep] = [r for r in results if isinstance(r, ReActStep)]
        entity = task.get("entity") or {}
        if not entity:
            entity = task.get("current_task", {}).get("entity") or {}
        target_entity_id = (
            task.get("target_entity_id")
            or task.get("entity_id")
            or entity.get("id")
        )

        claims: list[dict[str, Any]] = []
        now_iso = datetime.now(UTC).isoformat()

        for s in history:
            if s.error:
                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "investigation_error",
                        "object_value": {"tool": s.action, "error": s.error},
                        "source_url": "",
                        "confidence": 0.0,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )
                continue
            if s.observation is None or s.action == "finish":
                continue

            obs = s.observation
            data = obs.model_dump() if hasattr(obs, "model_dump") else (
                dict(obs) if isinstance(obs, dict) else {}
            )

            if s.action == "search_news_archive":
                for art in data.get("articles") or []:
                    if not isinstance(art, dict):
                        continue
                    priority = int(art.get("priority") or 2)
                    confidence = _PRIORITY_CONFIDENCE.get(priority, 0.55)
                    # Si la cita viene de citations, intentamos linkear el quote.
                    quote = (art.get("snippet") or "")[:500]
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "mentioned_in_press",
                            "object_value": {
                                "medium": art.get("source_domain"),
                                "title": art.get("title"),
                                "published_at": art.get("published_at"),
                                "quote": quote,
                                "priority": priority,
                                "kind": "investigation" if priority == 1 else "news",
                            },
                            "source_url": art.get("url") or "",
                            "confidence": confidence,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

            elif s.action == "wayback_machine":
                is_stub = bool(data.get("stub"))
                for snap in data.get("snapshots") or []:
                    if not isinstance(snap, dict):
                        continue
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "archived_at",
                            "object_value": {
                                "url": snap.get("url"),
                                "archived_url": snap.get("archived_url"),
                                "timestamp": snap.get("timestamp"),
                                "status": snap.get("status"),
                                "notes": {"stub": is_stub} if is_stub else {},
                            },
                            "source_url": snap.get("archived_url") or "",
                            "confidence": 0.55 if is_stub else 0.85,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

            elif s.action == "search_twitter_archive":
                is_stub = bool(data.get("stub"))
                for post in data.get("posts") or []:
                    if not isinstance(post, dict):
                        continue
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "social_post",
                            "object_value": {
                                "handle": post.get("handle"),
                                "posted_at": post.get("posted_at"),
                                "text": (post.get("text") or "")[:500],
                                "notes": {"stub": is_stub} if is_stub else {},
                            },
                            "source_url": post.get("archived_url")
                            or post.get("url")
                            or "",
                            "confidence": 0.40 if is_stub else 0.70,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

        return claims


__all__ = ["ElPeriodista"]
