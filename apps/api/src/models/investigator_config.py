from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

InvestigatorCallsign = Literal[
    "sabueso",
    "el-buscador",
    "la-tasadora",
    "el-contador",
    "el-letrado",
    "el-detective",
    "el-periodista",
    "la-jueza",
]


class InvestigatorConfig(BaseModel):
    """Una fila de investigator_configs. `config` queda como JSONB libre:
    el cliente valida el shape con Zod, la DB solo garantiza la PK."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    callsign: InvestigatorCallsign
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvestigatorConfigList(BaseModel):
    configs: list[InvestigatorConfig]


class ConfigPatch(BaseModel):
    """Body para PATCH /configs/{callsign}. Se hace shallow merge JSONB
    (`config = config || patch.config`) — los campos no presentes se
    mantienen, los nuevos se agregan, los repetidos se sobreescriben."""

    config: dict[str, Any] = Field(default_factory=dict)
