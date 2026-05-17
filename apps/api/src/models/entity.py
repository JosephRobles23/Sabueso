from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Country = Literal["pe", "cl", "mx", "sv"]
EntityType = Literal["person", "company", "government_entity", "contract"]


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    country: Country
    type: EntityType
    identifier: str | None = None
    name: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
