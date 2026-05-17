"""La Tasadora — investigadora de patrimonio (S-11).

Strategy: ReAct. Los PDFs de JNE son impredecibles (escaneados, texto
roto, secciones faltantes), así que necesitamos iterar: bajar el PDF,
parsear, identificar el DNI declarado, recién entonces consultar SUNARP.

``_claims_from_results`` consume el history (lista de ReActStep) y
emite claims con 3 predicates: ``patrimony_discrepancy`` cuando hay
desbalance, ``patrimony_match`` cuando coinciden, y ``property_observed``
por cada partida SUNARP.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
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
    """Resumen breve del history para el siguiente prompt de decisión."""
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


class LaTasadora(BaseInvestigator):
    """Investigadora de patrimonio (Perú: JNE PDF + SUNARP)."""

    callsign = "la-tasadora"
    role = "patrimony"
    color = "emerald-500"
    model = "deepseek/deepseek-v4-flash"
    strategy = Strategy.REACT
    allowed_tools = ["fetch_jne_hoja_vida", "query_sunarp_properties"]
    system_prompt_path = "tasadora"

    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("LaTasadora uses ReAct, not ReWOO")

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
        candidate_id = task.get("candidate_id") or entity.get("candidate_id") or ""

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
                f"- candidate_id JNE: {candidate_id or '(no provisto)'}\n\n"
                "Historial hasta ahora:\n"
                f"{_summarize_history(history)}\n\n"
                "Decidí el próximo step. Formato JSON estricto:\n"
                '{"thought":"...", "action":"<tool|finish>", "args":{...}}\n'
                "Tools permitidas: fetch_jne_hoja_vida, query_sunarp_properties.\n"
                "`action=\"finish\"` cuando tengas información suficiente o no haya "
                "más fuentes que probar."
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

        jne_data: dict[str, Any] | None = None
        sunarp_data: dict[str, Any] | None = None

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
            if s.action == "fetch_jne_hoja_vida":
                jne_data = data
            elif s.action == "query_sunarp_properties":
                sunarp_data = data

        # Emitimos los claims patrimoniales
        if sunarp_data is not None:
            properties = sunarp_data.get("properties") or []
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                value = prop.get("valor") or {}
                amount = value.get("amount") if isinstance(value, dict) else None
                currency = (
                    value.get("currency") if isinstance(value, dict) else None
                ) or "PEN"
                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "property_observed",
                        "object_value": {
                            "type": prop.get("type"),
                            "partida": prop.get("partida"),
                            "ubicacion": prop.get("ubicacion"),
                            "descripcion": prop.get("descripcion"),
                            "amount": amount,
                            "currency": currency,
                            "fecha_inscripcion": prop.get("fecha_inscripcion"),
                        },
                        "source_url": "https://www.sunarp.gob.pe",
                        "confidence": 0.85 if amount else 0.75,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )

        if jne_data is not None and sunarp_data is not None:
            declared = jne_data.get("properties_declared") or []
            observed = sunarp_data.get("properties") or []
            declared_amount = 0.0
            income = jne_data.get("income_declared")
            if isinstance(income, dict) and income.get("amount"):
                declared_amount = float(income["amount"])
            observed_amount = 0.0
            for p in observed:
                if isinstance(p, dict):
                    v = p.get("valor") or {}
                    a = v.get("amount") if isinstance(v, dict) else None
                    if a:
                        observed_amount += float(a)

            delta_pen = observed_amount - declared_amount
            delta_pct = (
                round((delta_pen / declared_amount) * 100.0, 2)
                if declared_amount > 0
                else None
            )

            # heurística de discrepancia: hay propiedades observadas y la
            # declaración trae menos items que las observadas, o el monto
            # observado supera al declarado por >50%.
            is_discrepancy = (
                bool(observed)
                and (
                    (declared and len(observed) > len(declared))
                    or (declared_amount > 0 and observed_amount > declared_amount * 1.5)
                    or (declared_amount == 0 and observed_amount > 0)
                )
            )
            predicate = "patrimony_discrepancy" if is_discrepancy else "patrimony_match"
            claims.append(
                {
                    "entity_id": target_entity_id,
                    "predicate": predicate,
                    "object_value": {
                        "declared_count": len(declared),
                        "observed_count": len(observed),
                        "declared_amount": declared_amount,
                        "observed_amount": observed_amount,
                        "delta_pen": round(delta_pen, 2),
                        "delta_pct": delta_pct,
                        "currency": "PEN",
                        "jne_dni": jne_data.get("dni"),
                    },
                    "source_url": "https://www.sunarp.gob.pe",
                    "confidence": 0.85 if is_discrepancy else 0.90,
                    "agent_callsign": self.callsign,
                    "created_at": now_iso,
                }
            )

        return claims


__all__ = ["LaTasadora"]
