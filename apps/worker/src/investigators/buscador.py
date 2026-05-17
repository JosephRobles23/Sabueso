"""El Buscador — investigador de reconocimiento (S-11).

Strategy: ReWOO. Resuelve identificadores (DNI, RUC) y mapea aliases
en registros públicos. Para cada identificador en la pista emite 1
step en paralelo:

- DNI → ``find_dni_record`` (RENIEC stub)
- RUC → ``find_ruc_record`` (SUNAT stub)
- nombre → ``search_manolo`` (visitas oficiales, fuente real)

``_claims_from_results`` traduce a 4 predicates posibles: ``is_dni``,
``is_ruc``, ``holds_position``, ``visited_official_entity``.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from ..llm.client import LLMResponse
from ..tools.registry import ToolDef
from .base import BaseInvestigator, Strategy

log = logging.getLogger(__name__)

DNI_RE = re.compile(r"^\d{8}$")
RUC_RE = re.compile(r"^\d{11}$")


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


def _classify_identifier(value: str) -> str:
    v = (value or "").strip()
    if DNI_RE.match(v):
        return "dni"
    if RUC_RE.match(v):
        return "ruc"
    return "name"


class ElBuscador(BaseInvestigator):
    """Investigador de reconocimiento (Perú: RENIEC stub + SUNAT stub + Manolo)."""

    callsign = "el-buscador"
    role = "recon"
    color = "slate-400"
    model = "moonshot/kimi-k2.6"
    strategy = Strategy.REWOO
    allowed_tools = ["search_manolo", "find_dni_record", "find_ruc_record"]
    system_prompt_path = "buscador"

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
                f"- entity_identifier: {entity_identifier or '(no provisto)'}\n"
                f"- país: {self.country}\n\n"
                "Devolvé SOLO JSON estricto con el plan ReWOO. Formato:\n"
                '{"steps":[{"tool":"<nombre>","args":{...}}, ...]}\n'
                "Reglas:\n"
                "- 1 step a `find_dni_record` si tenés DNI de 8 dígitos.\n"
                "- 1 step a `find_ruc_record` si tenés RUC de 11 dígitos.\n"
                "- 1 step a `search_manolo` con el nombre o el DNI.\n"
                "- Sin tools no listadas. Máximo 5 steps.\n"
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
        raise NotImplementedError("ElBuscador uses ReWOO, not ReAct")

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

            if tool == "find_dni_record":
                record = data.get("record") or {}
                is_stub = bool(record.get("stub"))
                found = bool(record.get("found"))
                confidence = (
                    0.95 if found and record.get("full_name") else
                    0.80 if found else
                    0.60 if is_stub else
                    0.40
                )
                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "is_dni",
                        "object_value": {
                            "dni": record.get("dni"),
                            "full_name": record.get("full_name"),
                            "birth_year": record.get("birth_year"),
                            "found": found,
                            "notes": {"stub": is_stub} if is_stub else {},
                        },
                        "source_url": "https://eldni.com" if not is_stub else "",
                        "confidence": confidence,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )

            elif tool == "find_ruc_record":
                record = data.get("record") or {}
                is_stub = bool(record.get("stub"))
                found = bool(record.get("found"))
                estado = record.get("estado")
                confidence = (
                    0.95 if found and record.get("razon_social") and estado == "ACTIVO" else
                    0.80 if found and record.get("razon_social") else
                    0.60 if is_stub else
                    0.40
                )
                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "is_ruc",
                        "object_value": {
                            "ruc": record.get("ruc"),
                            "razon_social": record.get("razon_social"),
                            "estado": estado,
                            "direccion": record.get("direccion"),
                            "found": found,
                            "notes": {"stub": is_stub} if is_stub else {},
                        },
                        "source_url": "https://e-consultaruc.sunat.gob.pe" if not is_stub else "",
                        "confidence": confidence,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )

            elif tool == "search_manolo":
                visits = data.get("visits") or []
                entities = sorted({v.get("entity") for v in visits if v.get("entity")})
                if visits:
                    # Aproximamos `holds_position` cuando aparece en >2 entidades
                    # oficiales distintas. Si no, sólo `visited_official_entity`.
                    primary_url = ""
                    for v in visits:
                        if v.get("source_url"):
                            primary_url = v["source_url"]
                            break
                    if len(entities) >= 2:
                        claims.append(
                            {
                                "entity_id": target_entity_id,
                                "predicate": "holds_position",
                                "object_value": {
                                    "entities": list(entities),
                                    "visit_count": len(visits),
                                },
                                "source_url": primary_url
                                or "https://www.manolo.pe/buscar",
                                "confidence": 0.80,
                                "agent_callsign": self.callsign,
                                "created_at": now_iso,
                            }
                        )
                    claims.append(
                        {
                            "entity_id": target_entity_id,
                            "predicate": "visited_official_entity",
                            "object_value": {
                                "query": data.get("query"),
                                "visit_count": len(visits),
                                "entities": list(entities),
                            },
                            "source_url": primary_url
                            or "https://www.manolo.pe/buscar",
                            "confidence": 0.80 if entities else 0.60,
                            "agent_callsign": self.callsign,
                            "created_at": now_iso,
                        }
                    )

        return claims


__all__ = ["ElBuscador"]
