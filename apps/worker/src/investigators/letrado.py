"""El Letrado — investigador normativo (S-11).

Strategy: ReWOO. Planea N consultas independientes en paralelo:

- ``query_legalize_pe`` para buscar normas/sentencias en el corpus.
- ``search_sentences`` (stub) para sentencias específicas.
- ``cross_vote_interest`` (stub) para cruzar votos del Congreso con
  bienes/empresas declaradas.

``_claims_from_results`` emite 4 predicates: ``voted_law``,
``has_sentence``, ``vote_interest_conflict`` y ``legal_mention``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ..llm.client import LLMResponse
from ..tools.registry import ToolDef
from .base import BaseInvestigator, Strategy

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


class ElLetrado(BaseInvestigator):
    """Investigador normativo (Perú: legalize-pe + sentencias + votos)."""

    callsign = "el-letrado"
    role = "legal"
    color = "sky-500"
    model = "deepseek/deepseek-v4-flash"
    strategy = Strategy.REWOO
    allowed_tools = ["query_legalize_pe", "search_sentences", "cross_vote_interest"]
    system_prompt_path = "letrado"

    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        entity = state.get("entity") or {}
        entity_identifier = (
            task.get("entity_identifier")
            or entity.get("identifier")
            or ""
        )
        entity_name = task.get("entity_name") or entity.get("name") or ""
        declared_assets = (
            task.get("declared_assets")
            or entity.get("declared_assets")
            or []
        )

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
                f"- entity_identifier (DNI): {entity_identifier or '(no provisto)'}\n"
                f"- declared_assets: {declared_assets or '(no provistos)'}\n\n"
                "Devolvé SOLO JSON estricto con el plan ReWOO. Formato:\n"
                '{"steps":[{"tool":"<nombre>","args":{...}}, ...]}\n'
                "Reglas:\n"
                "- 1 step a `query_legalize_pe` con `query=<nombre+contexto>`.\n"
                "- 1 step a `search_sentences` con el nombre (y DNI si lo tenés).\n"
                "- 1 step a `cross_vote_interest` SOLO si `declared_assets` no está vacío.\n"
                "- Sin tools fuera del permiso. Máximo 4 steps.\n"
                "Nada de prosa, sólo el JSON."
            ),
        }
        return [system_msg, user_msg]

    async def _react_decide_prompt(
        self,
        task: dict[str, Any],
        history: list[Any],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("ElLetrado uses ReWOO, not ReAct")

    def _claims_from_results(
        self,
        task: dict[str, Any],
        results: list[Any],
        synthesis: LLMResponse | None,
    ) -> list[dict[str, Any]]:
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

        for res in results:
            if not isinstance(res, dict):
                continue
            if "error" in res:
                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "investigation_error",
                        "object_value": {
                            "tool": res.get("tool", ""),
                            "error": str(res.get("error", "unknown")),
                        },
                        "source_url": "",
                        "confidence": 0.0,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )
                continue

            tool = res.get("tool", "")
            payload = res.get("result")
            if payload is None:
                continue
            data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)

            if tool == "query_legalize_pe":
                citations = data.get("results") or []
                for cit in citations:
                    if not isinstance(cit, dict):
                        continue
                    source = cit.get("source") or {}
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "legal_mention",
                            "object_value": {
                                "text": cit.get("text"),
                                "source_type": source.get("source_type"),
                                "title": source.get("title"),
                            },
                            "source_url": source.get("url") or "",
                            "confidence": 0.75,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

            elif tool == "search_sentences":
                is_stub = bool(data.get("stub"))
                sentences = data.get("sentences") or []
                for sent in sentences:
                    if not isinstance(sent, dict):
                        continue
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "has_sentence",
                            "object_value": {
                                "case_id": sent.get("case_id"),
                                "court": sent.get("court"),
                                "year": sent.get("year"),
                                "crime": sent.get("crime"),
                                "outcome": sent.get("outcome"),
                                "notes": {"stub": is_stub} if is_stub else {},
                            },
                            "source_url": sent.get("url") or "",
                            "confidence": 0.60 if is_stub else 0.85,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

            elif tool == "cross_vote_interest":
                is_stub = bool(data.get("stub"))
                conflicts = data.get("conflicts") or []
                for conflict in conflicts:
                    if not isinstance(conflict, dict):
                        continue
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "vote_interest_conflict",
                            "object_value": {
                                "law_number": conflict.get("law_number"),
                                "law_title": conflict.get("law_title"),
                                "vote": conflict.get("vote"),
                                "declared_asset": conflict.get("declared_asset"),
                                "overlap_reason": conflict.get("overlap_reason"),
                                "notes": {"stub": is_stub} if is_stub else {},
                            },
                            "source_url": "https://www.congreso.gob.pe",
                            "confidence": 0.60 if is_stub else 0.90,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

        return claims


__all__ = ["ElLetrado"]
