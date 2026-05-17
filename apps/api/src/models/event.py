from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "investigation_started",
    "plan_generated",
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


class InvestigationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    investigation_id: UUID
    type: EventType
    agent_callsign: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
