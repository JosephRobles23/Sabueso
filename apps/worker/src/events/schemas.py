"""Event schemas for the investigation SSE stream (S-08).

Each event is a discriminated union member on the ``type`` field. The worker
emits these via ``EventEmitter`` (inserts into ``investigation_events``);
the API streams the persisted rows back to the frontend via SSE. The 12
schemas here are the contract — they are also the input to ``pydantic2ts``
so the frontend gets the same shapes (see ``packages/shared-types/events.ts``).

The ``payload`` on the DB row is the discriminated union member with the
type stripped (the row stores type separately) — but the wire format that
SSE emits is the full union member, type included, so the frontend can
narrow with a single switch.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "investigation_started",
    "plan_generated",
    "preview_mode_warning",
    "agent_started",
    "tool_call",
    "claim_created",
    "edge_discovered",
    "agent_finished",
    "verification_done",
    "synthesis_started",
    "investigation_complete",
    "investigation_failed",
    "heartbeat",
]

AgentCallsign = Literal[
    "sabueso",
    "el-buscador",
    "la-tasadora",
    "el-contador",
    "el-letrado",
    "el-detective",
    "el-periodista",
    "la-jueza",
]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InvestigationStartedPayload(_Base):
    type: Literal["investigation_started"] = "investigation_started"
    investigation_id: UUID
    entity_id: UUID
    country: Literal["pe", "cl", "mx", "sv"]
    locale: str


class PlanStep(_Base):
    agent: AgentCallsign
    task: str
    priority: int = Field(ge=0)


class PlanGeneratedPayload(_Base):
    type: Literal["plan_generated"] = "plan_generated"
    plan: list[PlanStep]


PreviewWarningReason = Literal["limited_data_sources"]


class PreviewModeWarningPayload(_Base):
    """Emitido por el plan node cuando ``state.country != 'pe'`` (S-18).

    El frontend lo renderiza como banner amarillo "Modo Preview · datos
    limitados", explicando qué investigadores quedan activos.
    """

    type: Literal["preview_mode_warning"] = "preview_mode_warning"
    country: Literal["cl", "mx", "sv"]
    available_investigators: list[AgentCallsign]
    available_sources: list[str] = Field(default_factory=list)
    reason: PreviewWarningReason = "limited_data_sources"


class AgentStartedPayload(_Base):
    type: Literal["agent_started"] = "agent_started"
    agent: AgentCallsign
    task: str


class ToolCallPayload(_Base):
    type: Literal["tool_call"] = "tool_call"
    agent: AgentCallsign
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    cache_hit: bool = False
    duration_ms: int | None = None


class ClaimCreatedPayload(_Base):
    type: Literal["claim_created"] = "claim_created"
    claim_id: UUID
    entity_id: UUID
    predicate: str
    object_value: dict[str, Any] = Field(default_factory=dict)
    source_url: str
    confidence: float = Field(ge=0.0, le=1.0)
    agent: AgentCallsign


class EdgeDiscoveredPayload(_Base):
    type: Literal["edge_discovered"] = "edge_discovered"
    edge_id: UUID
    from_entity: UUID
    to_entity: UUID
    edge_type: str
    weight: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    agent: AgentCallsign | None = None


class AgentFinishedPayload(_Base):
    type: Literal["agent_finished"] = "agent_finished"
    agent: AgentCallsign
    claims_created: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    duration_ms: int = Field(ge=0)


class VerificationDonePayload(_Base):
    type: Literal["verification_done"] = "verification_done"
    claim_id: UUID
    verified: bool
    verifier_score: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class SynthesisStartedPayload(_Base):
    type: Literal["synthesis_started"] = "synthesis_started"
    claim_count: int = Field(ge=0)


class InvestigationCompletePayload(_Base):
    type: Literal["investigation_complete"] = "investigation_complete"
    dossier_url: str | None = None
    total_claims: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0.0)
    duration_ms: int = Field(ge=0)


class InvestigationFailedPayload(_Base):
    type: Literal["investigation_failed"] = "investigation_failed"
    error: str
    failed_agent: AgentCallsign | None = None
    partial_claims: int = Field(default=0, ge=0)


class HeartbeatPayload(_Base):
    type: Literal["heartbeat"] = "heartbeat"
    ts: datetime


EventPayload = Annotated[
    InvestigationStartedPayload
    | PlanGeneratedPayload
    | PreviewModeWarningPayload
    | AgentStartedPayload
    | ToolCallPayload
    | ClaimCreatedPayload
    | EdgeDiscoveredPayload
    | AgentFinishedPayload
    | VerificationDonePayload
    | SynthesisStartedPayload
    | InvestigationCompletePayload
    | InvestigationFailedPayload
    | HeartbeatPayload,
    Field(discriminator="type"),
]


_PAYLOAD_BY_TYPE: dict[EventType, type[_Base]] = {
    "investigation_started": InvestigationStartedPayload,
    "plan_generated": PlanGeneratedPayload,
    "preview_mode_warning": PreviewModeWarningPayload,
    "agent_started": AgentStartedPayload,
    "tool_call": ToolCallPayload,
    "claim_created": ClaimCreatedPayload,
    "edge_discovered": EdgeDiscoveredPayload,
    "agent_finished": AgentFinishedPayload,
    "verification_done": VerificationDonePayload,
    "synthesis_started": SynthesisStartedPayload,
    "investigation_complete": InvestigationCompletePayload,
    "investigation_failed": InvestigationFailedPayload,
    "heartbeat": HeartbeatPayload,
}


def validate_payload(event_type: EventType, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a payload dict against its schema and return the normalized dict.

    Used by the EventEmitter before insert. The type field is injected from
    ``event_type`` if missing so callers don't have to repeat themselves.
    """
    model = _PAYLOAD_BY_TYPE[event_type]
    data = {**payload, "type": event_type}
    return model.model_validate(data).model_dump(mode="json")


class StreamedEvent(_Base):
    """The full envelope the SSE endpoint emits to the client.

    The ``id`` is the BIGSERIAL PK on ``investigation_events`` — clients send it
    back as ``Last-Event-ID`` on reconnect to receive the backlog from there.
    """

    id: int
    investigation_id: UUID
    type: EventType
    agent_callsign: AgentCallsign | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


TERMINAL_EVENT_TYPES: frozenset[EventType] = frozenset(
    {"investigation_complete", "investigation_failed"}
)
