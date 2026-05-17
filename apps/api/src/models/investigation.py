from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.entity import Country

InvestigationStatus = Literal[
    "pending",
    "planning",
    "running",
    "verifying",
    "synthesizing",
    "complete",
    "failed",
    "cancelled",
]


class InvestigationCreate(BaseModel):
    entity_query: str = Field(min_length=2, max_length=200)
    country: Country
    locale: str = Field(default="es", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")

    @field_validator("entity_query")
    @classmethod
    def _strip_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("entity_query must not be blank")
        return stripped


class InvestigationCreated(BaseModel):
    investigation_id: UUID
    status: InvestigationStatus = "pending"
    entity_id: UUID


class Investigation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    target_entity_id: UUID
    country: Country
    locale: str
    status: InvestigationStatus
    plan: list[dict[str, Any]] = Field(default_factory=list)
    dossier_md: str | None = None
    cost_usd: float = 0.0
    progress_pct: int = 0
    is_public: bool = True
    started_at: datetime
    finished_at: datetime | None = None
