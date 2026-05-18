"""La Jueza — verificador Mixture-of-Agents (S-11).

NO hereda de BaseInvestigator porque su flujo no es ReWOO/ReAct. Sigue
el patrón MoA del C4 (decisión G4: siempre-on, no por threshold):

1. Por cada claim → 3 proposers en paralelo (sonnet-4.6 / kimi-k2.6 /
   gpt-4o) evalúan contra fuente primaria y devuelven verdict +
   confidence + checked_source_url.
2. Aggregator (sonnet-4.6) consume los 3 verdicts y produce el
   veredicto final con confidence_final calibrada y disagreements.

Si el batch tiene > 20 claims, se chunkea en grupos de 10 para no
inflar el contexto. Toda la corrida usa ``asyncio.gather`` —
verificar 20 claims debe terminar en ≤30s.

El método público ``verify_all`` matchea el ``InvestigatorRunner``
protocol del orchestrator: ``async (task, state) -> {claims, edges,
events}`` (sólo poblamos claims; edges quedan en []).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from ..llm.client import LLMClient, LLMResponse
from ..prompts.loader import PromptLoader
from .base import JSONParseError, parse_tolerant_json

log = logging.getLogger(__name__)

# Modelos del protocolo MoA (C4 §G4)
PROPOSERS: tuple[str, ...] = (
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-4o",
)
AGGREGATOR: str = "anthropic/claude-sonnet-4.6"

DEFAULT_CHUNK_SIZE = 10
LARGE_BATCH_THRESHOLD = 20
PROPOSER_TIMEOUT_S = 30.0


def _verdict_default() -> dict[str, Any]:
    return {
        "verdict": "uncertain",
        "confidence": 0.0,
        "rationale": "(no se pudo evaluar)",
        "checked_source_url": None,
    }


def _calibrate_confidence(verdicts: list[dict[str, Any]]) -> tuple[bool, float]:
    """Aggregator local: calibra confidence_final + verified a partir de los
    3 verdicts. Es el mismo mapeo descrito en jueza_moa_system.md y sirve
    de fallback cuando el aggregator LLM no responde JSON parseable.
    """
    if not verdicts:
        return False, 0.20
    supports = sum(1 for v in verdicts if v.get("verdict") == "support")
    refutes = sum(1 for v in verdicts if v.get("verdict") == "refute")
    uncertains = sum(1 for v in verdicts if v.get("verdict") == "uncertain")

    if refutes >= 1:
        return False, 0.25
    if supports == 3:
        urls = {v.get("checked_source_url") for v in verdicts if v.get("checked_source_url")}
        return True, 0.92 if len(urls) >= 2 else 0.80
    if supports == 2 and uncertains == 1:
        return True, 0.60
    if supports == 1 and uncertains == 2:
        return False, 0.45
    if uncertains == 3:
        return False, 0.20
    return False, 0.40


class LaJueza:
    """Verificador MoA. ``verify_all`` es el entrypoint del orchestrator."""

    callsign = "la-jueza"
    role = "verifier"
    proposers: tuple[str, ...] = PROPOSERS
    aggregator: str = AGGREGATOR

    def __init__(
        self,
        *,
        country: str = "pe",
        locale: str = "es",
        llm: LLMClient,
        prompt_loader: PromptLoader | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        large_batch_threshold: int = LARGE_BATCH_THRESHOLD,
        proposer_timeout_s: float = PROPOSER_TIMEOUT_S,
    ) -> None:
        self.country = country
        self.locale = locale
        self.llm = llm
        self.prompts = prompt_loader or PromptLoader()
        self.chunk_size = chunk_size
        self.large_batch_threshold = large_batch_threshold
        self.proposer_timeout_s = proposer_timeout_s

    # ------------------------------------------------------------------ public
    async def verify_all(
        self, task: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        """Verifica todos los claims del state. Matchea el InvestigatorRunner
        protocol del orchestrator: ``(task, state) → {claims, edges, events}``.
        """
        claims: list[dict[str, Any]] = list(state.get("claims") or [])
        events: list[dict[str, Any]] = [
            {
                "type": "verification_started",
                "agent": self.callsign,
                "payload": {"claims_total": len(claims)},
            }
        ]

        if not claims:
            events.append(
                {
                    "type": "verification_done",
                    "agent": self.callsign,
                    "payload": {"verified": 0},
                }
            )
            return {"claims": [], "edges": [], "events": events}

        # Chunking si el batch es grande
        if len(claims) > self.large_batch_threshold:
            chunks = [
                claims[i : i + self.chunk_size]
                for i in range(0, len(claims), self.chunk_size)
            ]
        else:
            chunks = [claims]

        verified: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_results = await asyncio.gather(
                *[self._verify_one(c, state) for c in chunk],
                return_exceptions=True,
            )
            for orig, res in zip(chunk, chunk_results, strict=True):
                if isinstance(res, Exception):
                    log.exception("jueza.verify_one failed: %s", res)
                    verified.append(self._unverified_passthrough(orig, str(res)))
                    events.append(
                        {
                            "type": "verification_error",
                            "agent": self.callsign,
                            "payload": {
                                "claim_predicate": orig.get("predicate"),
                                "error": str(res),
                            },
                        }
                    )
                else:
                    verified.append(res)
                    events.append(
                        {
                            "type": "verification_done",
                            "agent": self.callsign,
                            "payload": {
                                "predicate": orig.get("predicate"),
                                "verified": res.get("verified"),
                                "verifier_score": res.get("confidence_final"),
                            },
                        }
                    )

        events.append(
            {
                "type": "verification_batch_done",
                "agent": self.callsign,
                "payload": {
                    "total": len(claims),
                    "verified": sum(1 for v in verified if v.get("verified")),
                },
            }
        )
        # Retornamos `claims` (que el orchestrator usará como verified_claims
        # vía _normalize_result en placeholders.make_jueza_node).
        return {"claims": verified, "edges": [], "events": events}

    # ------------------------------------------------------------------ helpers
    async def _verify_one(
        self, claim: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        proposer_coros: list[Awaitable[LLMResponse]] = [
            self.llm.complete(
                model=model,
                messages=self._proposer_messages(model, claim, state),
                state=state,
            )
            for model in self.proposers
        ]
        raw_responses = await asyncio.gather(*proposer_coros, return_exceptions=True)

        verdicts: list[dict[str, Any]] = []
        for model, resp in zip(self.proposers, raw_responses, strict=True):
            if isinstance(resp, Exception):
                log.warning("proposer.%s.error: %s", model, resp)
                v = _verdict_default()
                v["proposer"] = model
                verdicts.append(v)
                continue
            try:
                parsed = parse_tolerant_json(resp.text)
            except JSONParseError as exc:
                log.warning("proposer.%s.json_parse_error: %s", model, exc)
                v = _verdict_default()
                v["proposer"] = model
                verdicts.append(v)
                continue
            if not isinstance(parsed, dict):
                v = _verdict_default()
                v["proposer"] = model
                verdicts.append(v)
                continue
            parsed.setdefault("verdict", "uncertain")
            parsed.setdefault("confidence", 0.0)
            parsed.setdefault("rationale", "")
            parsed.setdefault("checked_source_url", None)
            parsed["proposer"] = model
            verdicts.append(parsed)

        # Aggregator LLM (con fallback a calibración local)
        verified_default, conf_default = _calibrate_confidence(verdicts)
        try:
            agg_resp = await asyncio.wait_for(
                self.llm.complete(
                    model=self.aggregator,
                    messages=self._aggregator_messages(claim, verdicts, state),
                    state=state,
                ),
                timeout=self.proposer_timeout_s,
            )
            agg_data = parse_tolerant_json(agg_resp.text)
            if not isinstance(agg_data, dict):
                raise JSONParseError("aggregator returned non-object")
            verified = bool(agg_data.get("verified", verified_default))
            confidence_final = float(agg_data.get("confidence_final", conf_default))
            disagreements = list(agg_data.get("disagreements") or [])
            verifier_notes = str(
                agg_data.get("verifier_notes") or "(sin notas)"
            )
        except (TimeoutError, JSONParseError, Exception) as exc:
            log.warning("aggregator fallback (local calibration): %s", exc)
            verified = verified_default
            confidence_final = conf_default
            disagreements = [
                {
                    "proposer": v.get("proposer"),
                    "verdict": v.get("verdict"),
                    "rationale": v.get("rationale"),
                }
                for v in verdicts
                if v.get("verdict") != "support"
            ]
            verifier_notes = (
                f"Aggregator unavailable; calibración local: "
                f"{sum(1 for v in verdicts if v.get('verdict') == 'support')}/3 support"
            )

        original_confidence = float(claim.get("confidence") or 0.0)
        return {
            **claim,
            "verified": verified,
            "confidence_final": round(confidence_final, 4),
            "confidence_original": original_confidence,
            "disagreements": disagreements,
            "verifier_notes": verifier_notes,
            "verified_at": datetime.now(UTC).isoformat(),
            "verified_by_jueza": True,
            "verifier_score": round(confidence_final, 4),
        }

    def _unverified_passthrough(
        self, claim: dict[str, Any], error: str
    ) -> dict[str, Any]:
        return {
            **claim,
            "verified": False,
            "confidence_final": round(float(claim.get("confidence") or 0.0), 4),
            "confidence_original": float(claim.get("confidence") or 0.0),
            "disagreements": [],
            "verifier_notes": f"verifier_error: {error}",
            "verified_at": datetime.now(UTC).isoformat(),
            "verified_by_jueza": False,
            "verifier_score": 0.0,
        }

    # ------------------------------------------------------------------ prompts
    def _system_prompt(self, variables: dict[str, Any] | None = None) -> str:
        loaded = self.prompts.load(
            "jueza_moa",
            variables={
                "country": self.country,
                "locale": self.locale,
                **(variables or {}),
            },
        )
        return loaded.body

    def _proposer_messages(
        self,
        model: str,
        claim: dict[str, Any],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        entity = state.get("entity") or {}
        target_id = state.get("target_entity_id") or claim.get("entity_id") or ""
        system = self._system_prompt(
            {"claim": "<por venir en user>", "verdicts": "[N/A: proposer]"}
        )
        user = (
            f"Sos el proposer `{model}`. Evaluá el siguiente claim contra "
            "fuente primaria y devolvé SOLO JSON estricto.\n\n"
            f"Entity: id={target_id} name={entity.get('name', '(no provisto)')}\n"
            f"Claim:\n```json\n{json.dumps(claim, ensure_ascii=False, default=str)}\n```\n\n"
            'Formato esperado: {"verdict":"support|refute|uncertain",'
            '"confidence":0..1,"rationale":"...","checked_source_url":"<url|null>"}'
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _aggregator_messages(
        self,
        claim: dict[str, Any],
        verdicts: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        system = self._system_prompt(
            {"claim": "<en user>", "verdicts": "<en user>"}
        )
        claim_json = json.dumps(claim, ensure_ascii=False, default=str)
        verdicts_json = json.dumps(verdicts, ensure_ascii=False, default=str)
        user = (
            "Sos el aggregator del MoA. Recibís 3 verdicts y debés producir "
            "el veredicto final.\n\n"
            f"Claim original:\n```json\n{claim_json}\n```\n\n"
            f"Verdicts:\n```json\n{verdicts_json}\n```\n\n"
            "Devolvé SOLO JSON estricto. Formato:\n"
            '{"verified":true|false,"confidence_final":0..1,'
            '"disagreements":[{"proposer":"...","verdict":"...","rationale":"..."}],'
            '"verifier_notes":"<síntesis breve>"}'
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


# Adaptador para conectar con el InvestigatorRunner protocol del
# orchestrator. ``deps.jueza_runner`` espera ``(task, state) → Any``.
def make_jueza_runner(jueza: LaJueza) -> Callable[
    [dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]
]:
    return jueza.verify_all


__all__ = [
    "LaJueza",
    "make_jueza_runner",
    "PROPOSERS",
    "AGGREGATOR",
]
