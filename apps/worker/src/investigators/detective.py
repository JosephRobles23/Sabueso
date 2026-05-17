"""El Detective — investigador de relaciones (S-11).

Strategy: ReAct. Cada lookup abre nuevos seeds, así que iteramos:

- ``find_relatives`` — BFS sobre el grafo familia.
- ``query_sunarp_board`` (stub) — directorios y socios SUNARP.
- ``expand_network`` (stub) — expansión genérica multi-fuente.

El Detective genera principalmente **edges**, no claims. Por eso
``_claims_from_results`` retorna ``{"claims": [], "edges": [...]}``
— el orchestrator acepta este shape vía ``_normalize_result``.
"""

from __future__ import annotations

import logging
from typing import Any

from ..llm.client import LLMResponse
from ..tools.registry import ToolDef
from .base import BaseInvestigator, ReActStep, Strategy

log = logging.getLogger(__name__)


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


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mergeá edges idénticos por (source, target, edge_type) manteniendo la
    confidence más alta."""
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in edges:
        key = (
            str(e.get("source") or ""),
            str(e.get("target") or ""),
            str(e.get("edge_type") or ""),
        )
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = e
            continue
        prev_conf = float((prev.get("extra") or {}).get("confidence") or 0.0)
        new_conf = float((e.get("extra") or {}).get("confidence") or 0.0)
        if new_conf > prev_conf:
            by_key[key] = e
    return list(by_key.values())


class ElDetective(BaseInvestigator):
    """Investigador de relaciones (Perú: family + SUNARP board + network)."""

    callsign = "el-detective"
    role = "relationships"
    color = "rose-500"
    model = "deepseek/deepseek-v4-flash"
    strategy = Strategy.REACT
    allowed_tools = ["find_relatives", "query_sunarp_board", "expand_network"]
    system_prompt_path = "detective"

    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("ElDetective uses ReAct, not ReWOO")

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
                f"- entity_identifier (DNI/RUC seed): {entity_identifier or '(no provisto)'}\n\n"
                "Historial hasta ahora:\n"
                f"{_summarize_history(history)}\n\n"
                "Decidí el próximo step. Formato JSON estricto:\n"
                '{"thought":"...", "action":"<tool|finish>", "args":{...}}\n'
                "Tools permitidas: find_relatives, query_sunarp_board, expand_network.\n"
                "`action=\"finish\"` cuando hayas mapeado la red (2 grados) o "
                "los lookups dejen de aportar nuevos vínculos."
            ),
        }
        return [system_msg, user_msg]

    def _claims_from_results(
        self,
        task: dict[str, Any],
        results: list[Any],  # ReActStep list
        synthesis: LLMResponse | None,
    ) -> dict[str, Any]:
        """Devuelve {"claims": [], "edges": [...]} — el orchestrator
        acepta este shape gracias a _normalize_result en placeholders.py."""
        history: list[ReActStep] = [r for r in results if isinstance(r, ReActStep)]
        entity = task.get("entity") or {}
        if not entity:
            entity = task.get("current_task", {}).get("entity") or {}
        seed = (
            task.get("entity_identifier")
            or entity.get("identifier")
            or ""
        )

        edges: list[dict[str, Any]] = []

        for s in history:
            if s.action == "finish" or s.observation is None or s.error:
                continue
            obs = s.observation
            data = obs.model_dump() if hasattr(obs, "model_dump") else (
                dict(obs) if isinstance(obs, dict) else {}
            )

            if s.action == "find_relatives":
                root = data.get("root_dni") or seed
                for rel in data.get("relatives") or []:
                    if not isinstance(rel, dict):
                        continue
                    edges.append(
                        {
                            "source": root,
                            "target": rel.get("dni") or rel.get("name") or "",
                            "edge_type": rel.get("relation") or "relative_of",
                            "source_url": "internal://entities",
                            "depth": int(rel.get("degree") or 1),
                            "agent_callsign": self.callsign,
                            "extra": {
                                "confidence": 0.85,
                                "name": rel.get("name"),
                            },
                        }
                    )

            elif s.action == "query_sunarp_board":
                is_stub = bool(data.get("stub"))
                for member in data.get("members") or []:
                    if not isinstance(member, dict):
                        continue
                    edges.append(
                        {
                            "source": member.get("dni") or member.get("name") or "",
                            "target": member.get("company_ruc")
                            or member.get("company_name")
                            or seed,
                            "edge_type": (member.get("role") or "director") + "_of",
                            "source_url": "https://www.sunarp.gob.pe",
                            "depth": 1,
                            "agent_callsign": self.callsign,
                            "extra": {
                                "confidence": 0.70 if is_stub else 0.85,
                                "stub": is_stub,
                                "name": member.get("name"),
                            },
                        }
                    )

            elif s.action == "expand_network":
                is_stub = bool(data.get("stub"))
                for raw in data.get("edges") or []:
                    if not isinstance(raw, dict):
                        continue
                    edges.append(
                        {
                            "source": raw.get("source", ""),
                            "target": raw.get("target", ""),
                            "edge_type": raw.get("edge_type") or "related_to",
                            "source_url": raw.get("source_url")
                            or "internal://network",
                            "depth": int(raw.get("depth") or 1),
                            "agent_callsign": self.callsign,
                            "extra": {
                                "confidence": 0.70 if is_stub else 0.80,
                                "stub": is_stub,
                            },
                        }
                    )

        return {"claims": [], "edges": _dedupe_edges(edges)}


__all__ = ["ElDetective"]
