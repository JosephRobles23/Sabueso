"""Nodo 6: synthesize — Claude Opus 4.7 produce dossier final en Markdown.

Es el único nodo que toca Opus (~$15/M tokens). Una sola llamada. El
prompt empuja al modelo a producir un dossier estructurado con secciones:
resumen, hallazgos, evidencia, contradicciones, próximos pasos.

Si Opus falla (timeout, 5xx), generamos un dossier mínimo con los claims
crudos formateados — la investigación no debería quedarse sin output
final por un blip de red.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ...llm.client import LLMClient
from ..state import InvestigationState

_Node = Callable[[InvestigationState], Awaitable[dict[str, Any]]]

log = logging.getLogger(__name__)

DEFAULT_SYNTH_MODEL = "anthropic/claude-opus-4.7"

SYSTEM_PROMPT = """Eres Sabueso, redactor en jefe. Tu tarea: sintetizar los
hallazgos de tu equipo en un dossier investigativo en Markdown.

Reglas:
- Idioma del dossier: {locale}.
- Cada afirmación debe tener cita ([source_url]).
- Nunca afirmes delito; solo "patrones consistentes con…".
- Si dos claims se contradicen, decilo explícitamente.

Estructura obligatoria:
# Dossier · {entity_name}

## Resumen ejecutivo
(3–5 bullets con los hallazgos principales)

## Hallazgos por dimensión
### Patrimonio
### Contratos públicos
### Trayectoria legislativa / judicial
### Red de relaciones
### Cobertura mediática

## Evidencia clave
(lista de claims con confidence ≥ 0.7)

## Contradicciones y dudas
(claims con confidence < 0.5 o que se contradicen)

## Próximos pasos sugeridos
"""

USER_TEMPLATE = """Hay {claim_count} claims y {edge_count} edges para sintetizar.

Claims:
{claims_block}

Edges:
{edges_block}

Generá el dossier en Markdown completo."""


@dataclass
class SynthesizeDeps:
    llm: LLMClient
    synth_model: str = DEFAULT_SYNTH_MODEL


def make_synthesize_node(deps: SynthesizeDeps) -> _Node:
    async def synthesize(state: InvestigationState) -> dict[str, Any]:
        claims = state.get("claims") or []
        edges = state.get("edges") or []
        entity = state.get("entity") or {}
        locale = state.get("locale", "es")
        entity_name = entity.get("name") or state.get("target_entity_id", "(desconocido)")

        system = SYSTEM_PROMPT.format(locale=locale, entity_name=entity_name)
        user = USER_TEMPLATE.format(
            claim_count=len(claims),
            edge_count=len(edges),
            claims_block=_render_claims(claims),
            edges_block=_render_edges(edges),
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        try:
            resp = await deps.llm.complete(
                model=deps.synth_model,
                messages=messages,
                state=state,  # type: ignore[arg-type]
            )
            dossier = (resp.text or "").strip()
            if not dossier:
                dossier = _fallback_dossier(entity_name, claims, edges)
        except Exception as exc:
            log.error("synthesize.llm_error: %s", exc)
            dossier = _fallback_dossier(entity_name, claims, edges)

        return {
            "status": "synthesizing",
            "dossier_md": dossier,
            "events": [
                {
                    "type": "synthesis_started",
                    "agent": "sabueso",
                    "payload": {"claim_count": len(claims)},
                }
            ],
        }

    return synthesize


def _render_claims(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "(sin claims)"
    lines = []
    for c in claims:
        agent = c.get("agent_callsign") or c.get("agent") or "?"
        pred = c.get("predicate", "?")
        obj = c.get("object_value", {})
        src = c.get("source_url") or c.get("source_id") or ""
        conf = c.get("confidence", 0.0)
        lines.append(
            f"- [{agent}] {pred} = {obj} (confidence={conf}, source={src})"
        )
    return "\n".join(lines)


def _render_edges(edges: list[dict[str, Any]]) -> str:
    if not edges:
        return "(sin edges)"
    return "\n".join(
        f"- {e.get('from_entity', '?')} —{e.get('type', '?')}→ {e.get('to_entity', '?')}"
        for e in edges
    )


def _fallback_dossier(
    entity_name: str,
    claims: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> str:
    return (
        f"# Dossier · {entity_name}\n\n"
        f"## Resumen ejecutivo\n"
        f"- Investigación completada con {len(claims)} claims y {len(edges)} edges.\n"
        f"- Síntesis automática no disponible (fallback).\n\n"
        f"## Evidencia cruda\n"
        f"{_render_claims(claims)}\n\n"
        f"## Edges\n"
        f"{_render_edges(edges)}\n"
    )
