"""El Contador — investigador de contrataciones públicas (S-10).

Strategy: ReWOO. El LLM planifica con 1 step por RUC, ``search_seace_contracts``
corre en paralelo, luego ``_claims_from_results`` aplana cada release OCDS en
1 claim ``awarded_contract`` + 1 claim sumario ``total_contracts_awarded`` por RUC.

La confianza se calibra contra el match exacto del RUC: si el RUC pedido
coincide con el del party del release, confidence sube; si sólo aparece
por coincidencia textual en buyer/supplier, baja.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ..llm.client import LLMResponse
from ..tools.registry import ToolDef
from .base import BaseInvestigator, Strategy

log = logging.getLogger(__name__)

SEACE_TOOL = "search_seace_contracts"
HIGH_VALUE_THRESHOLD_PEN = 1_000_000.0


def _tool_catalog_lines(tools: list[ToolDef[Any, Any]]) -> str:
    """Render the tools available to El Contador en una sola línea por tool.

    Se inyecta en el prompt en BREAKPOINT 3 para que el modelo conozca las
    firmas reales. Mantenemos la línea breve para no saturar el contexto.
    """
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


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _year_from_date(s: Any) -> int | None:
    if not isinstance(s, str) or not s:
        return None
    head = s.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(head, fmt).year
        except ValueError:
            continue
    if len(head) >= 4 and head[:4].isdigit():
        return int(head[:4])
    return None


def _contract_to_dict(c: Any) -> dict[str, Any]:
    """Coerce SeaceContract Pydantic model or plain dict to a dict view."""
    if hasattr(c, "model_dump"):
        dumped: dict[str, Any] = c.model_dump()
        return dumped
    if isinstance(c, dict):
        return c
    return {}


def _source_url_for(ruc: str, contract: dict[str, Any]) -> str:
    explicit = contract.get("url")
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"https://contratacionesabiertas.osce.gob.pe/buscador-de-contrataciones?ruc={ruc}"


def _confidence_for(*, ruc: str, contract: dict[str, Any]) -> tuple[float, str]:
    """Return (confidence, match_reason).

    Heurística:
    - 0.90 si el RUC pedido aparece como identifier de buyer/supplier y hay
      monto + fecha parseables.
    - 0.75 si el RUC coincide pero falta monto o fecha.
    - 0.60 si el RUC sólo aparece por coincidencia textual en buyer/supplier
      name.
    - 0.40 si los campos centrales (monto/fecha) están todos vacíos.
    """
    buyer = (contract.get("buyer") or "") if isinstance(contract.get("buyer"), str) else ""
    supplier = (
        (contract.get("supplier") or "") if isinstance(contract.get("supplier"), str) else ""
    )
    value = contract.get("value")
    amount = None
    if isinstance(value, dict):
        amount = _safe_float(value.get("amount"))
    elif value is not None and hasattr(value, "amount"):
        amount = _safe_float(getattr(value, "amount", None))
    year = _year_from_date(contract.get("award_date"))
    has_amount = bool(amount and amount > 0)
    has_year = year is not None

    # SEACE no siempre expone el RUC del party en SeaceContract; al menos
    # confirmamos que aparece textualmente.
    ruc_in_text = ruc in f"{buyer} {supplier}"

    if has_amount and has_year:
        return (0.90 if ruc_in_text else 0.85, "ruc_match" if ruc_in_text else "amount_date_ok")
    if has_amount or has_year:
        return (0.75, "partial_fields")
    if ruc_in_text:
        return (0.60, "ruc_text_only")
    return (0.40, "fields_missing")


class ElContador(BaseInvestigator):
    """Investigador de contrataciones públicas (Perú: SEACE/OECE)."""

    callsign = "el-contador"
    role = "contracts"
    color = "violet-500"
    model = "anthropic/claude-sonnet-4.6"
    strategy = Strategy.REWOO
    allowed_tools = [SEACE_TOOL]
    system_prompt_path = "contador"

    async def _plan_prompt(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Build the planning prompt.

        System message lleva el prompt completo (Jinja-rendered con
        entity_identifier, entity_name, tool_catalog). El user message
        recapitula la pista y exige JSON estricto del shape ReWOO plan.
        """
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
                f"- entity_identifier (RUC esperado): {entity_identifier or '(no provisto)'}\n"
                f"- país: {self.country}\n\n"
                "Devolvé SOLO JSON estricto con el plan ReWOO. Formato:\n"
                '{"steps":[{"tool":"search_seace_contracts",'
                '"args":{"ruc":"<11 dígitos>","year_from":<int>,"year_to":<int>}}]}\n'
                "Reglas:\n"
                "- 1 step por RUC distinto a investigar.\n"
                "- Si no hay RUC concreto, usá el entity_identifier; si tampoco "
                "está, omití el plan (devolvé steps vacío).\n"
                "- year_from por defecto 2020; year_to el año actual.\n"
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
        # El Contador es ReWOO; este método está acá para satisfacer la
        # interfaz abstracta. No se llama en runtime con strategy=REWOO.
        raise NotImplementedError("ElContador uses ReWOO, not ReAct")

    def _claims_from_results(
        self,
        task: dict[str, Any],
        results: list[Any],
        synthesis: LLMResponse | None,
    ) -> list[dict[str, Any]]:
        """Map SEACE results → claims.

        Cada result viene del runner ReWOO como
        ``{"tool": "search_seace_contracts", "result": SeaceOutput}`` o
        ``{"tool": ..., "error": "..."}`` si el step falló. SeaceOutput es un
        Pydantic model; lo aplanamos con model_dump().
        """
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
                            "tool": res.get("tool", SEACE_TOOL),
                            "error": str(res.get("error", "unknown")),
                        },
                        "source_url": "",
                        "confidence": 0.0,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )
                continue

            payload = res.get("result")
            if payload is None:
                continue
            data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
            ruc = str(data.get("ruc") or "")
            contracts = data.get("contracts") or []
            sources = data.get("sources") or []
            primary_source_url = ""
            if sources and isinstance(sources[0], dict):
                primary_source_url = sources[0].get("url") or ""

            running_total = 0.0
            year_from: int | None = None
            year_to: int | None = None

            for raw in contracts:
                contract = _contract_to_dict(raw)
                value = contract.get("value")
                amount = None
                currency = "PEN"
                if isinstance(value, dict):
                    amount = _safe_float(value.get("amount"))
                    currency = value.get("currency") or "PEN"
                elif value is not None:
                    amount = _safe_float(getattr(value, "amount", None))
                    currency = getattr(value, "currency", None) or "PEN"

                year = _year_from_date(contract.get("award_date"))
                if amount is not None:
                    running_total += amount
                if year is not None:
                    year_from = year if year_from is None else min(year_from, year)
                    year_to = year if year_to is None else max(year_to, year)

                confidence, match_reason = _confidence_for(ruc=ruc, contract=contract)
                notes: dict[str, Any] = {"match_reason": match_reason}
                if amount is not None and amount > HIGH_VALUE_THRESHOLD_PEN:
                    notes["high_value"] = True

                claims.append(
                    {
                        "entity_id": target_entity_id,
                        "predicate": "awarded_contract",
                        "object_value": {
                            "ocid": contract.get("ocid"),
                            "title": contract.get("title"),
                            "buyer": contract.get("buyer"),
                            "supplier": contract.get("supplier"),
                            "amount": amount,
                            "currency": currency,
                            "year": year,
                            "award_date": contract.get("award_date"),
                            "ruc": ruc,
                            "notes": notes,
                        },
                        "source_url": _source_url_for(ruc, contract),
                        "confidence": confidence,
                        "agent_callsign": self.callsign,
                        "created_at": now_iso,
                    }
                )

            # Sumario: siempre 1 claim por RUC analizado.
            total_amount = data.get("total_amount")
            if isinstance(total_amount, dict):
                summary_amount = _safe_float(total_amount.get("amount")) or running_total
                summary_currency = total_amount.get("currency") or "PEN"
            else:
                summary_amount = running_total
                summary_currency = "PEN"

            summary_confidence = 0.90 if contracts else 0.85
            claims.append(
                {
                    "entity_id": target_entity_id,
                    "predicate": "total_contracts_awarded",
                    "object_value": {
                        "ruc": ruc,
                        "count": len(contracts),
                        "total_amount": round(summary_amount, 2),
                        "currency": summary_currency,
                        "year_from": year_from,
                        "year_to": year_to,
                    },
                    "source_url": primary_source_url
                    or f"https://contratacionesabiertas.osce.gob.pe/buscador-de-contrataciones?ruc={ruc}",
                    "confidence": summary_confidence,
                    "agent_callsign": self.callsign,
                    "created_at": now_iso,
                }
            )

        return claims


__all__ = ["ElContador"]
