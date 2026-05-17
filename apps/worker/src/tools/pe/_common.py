"""Tipos compartidos entre las tools PE."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Referencia a una fuente concreta. Se materializa luego en ``sources``."""

    url: str
    source_type: str
    title: str | None = None
    snapshot_at: datetime | None = None
    content_hash: str | None = None
    content_storage: str | None = None


class Citation(BaseModel):
    """Hallazgo individual con extracto + fuente. Lo que después se convierte en
    un ``claim`` después del paso de verificación."""

    text: str = Field(..., max_length=500)
    source: Source
    extracted_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Money(BaseModel):
    amount: float
    currency: str = "PEN"


class DateRange(BaseModel):
    start: date | None = None
    end: date | None = None
