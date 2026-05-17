"""Stub tools registradas para S-11.

Algunos investigadores referencian fuentes que en S-11 todavía no tienen
scraper/cliente real (sentencias del CGR, votos del Congreso, board de
empresas, Wayback Machine, Twitter Archive). Para que los runners ReWOO
puedan emitir un plan completo sin caerse por ``ToolPermissionError`` y
para que ReAct pueda observar resultados deterministas en tests, las
exponemos acá como handlers que devuelven payloads vacíos pero válidos
con la forma del output que los investigadores esperan.

Cada stub mantiene el contrato de input/output con Pydantic y devuelve
``stub=True`` en el payload para que ``_claims_from_results`` pueda
distinguir un resultado real de uno stub y bajar la confidence.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from ..registry import ToolRegistry
from ._common import Citation

DNI_RE = re.compile(r"^\d{8}$")
RUC_RE = re.compile(r"^\d{11}$")


# --------------------------------------------------------------- find_dni_record
class FindDniInput(BaseModel):
    dni: str = Field(..., min_length=8, max_length=8)

    @field_validator("dni")
    @classmethod
    def _dni(cls, v: str) -> str:
        v = v.strip()
        if not DNI_RE.match(v):
            raise ValueError("DNI debe tener 8 dígitos.")
        return v


class DniRecord(BaseModel):
    dni: str
    full_name: str | None = None
    birth_year: int | None = None
    found: bool = False
    stub: bool = True


class FindDniOutput(BaseModel):
    record: DniRecord
    citations: list[Citation] = Field(default_factory=list)


@ToolRegistry.register(
    country="pe",
    input_model=FindDniInput,
    output_model=FindDniOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "reniec"),
)
async def find_dni_record(payload: FindDniInput) -> FindDniOutput:
    """Stub para consulta RENIEC por DNI. Devuelve found=false sin red.

    La integración real (RENIEC vía SUNAT/Reniec API) llegará en S-12.
    Mantenemos el contrato para que El Buscador pueda emitir el plan.
    """
    return FindDniOutput(
        record=DniRecord(dni=payload.dni, found=False, stub=True),
        citations=[],
    )


# --------------------------------------------------------------- find_ruc_record
class FindRucInput(BaseModel):
    ruc: str = Field(..., min_length=11, max_length=11)

    @field_validator("ruc")
    @classmethod
    def _ruc(cls, v: str) -> str:
        v = v.strip()
        if not RUC_RE.match(v):
            raise ValueError("RUC debe tener 11 dígitos.")
        return v


class RucRecord(BaseModel):
    ruc: str
    razon_social: str | None = None
    estado: str | None = None
    direccion: str | None = None
    found: bool = False
    stub: bool = True


class FindRucOutput(BaseModel):
    record: RucRecord
    citations: list[Citation] = Field(default_factory=list)


@ToolRegistry.register(
    country="pe",
    input_model=FindRucInput,
    output_model=FindRucOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "sunat"),
)
async def find_ruc_record(payload: FindRucInput) -> FindRucOutput:
    """Stub para consulta SUNAT por RUC. Devuelve found=false sin red."""
    return FindRucOutput(
        record=RucRecord(ruc=payload.ruc, found=False, stub=True),
        citations=[],
    )


# --------------------------------------------------------------- search_sentences
class SearchSentencesInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    dni: str | None = None
    limit: int = Field(20, ge=1, le=100)


class Sentence(BaseModel):
    case_id: str | None = None
    court: str | None = None
    year: int | None = None
    crime: str | None = None
    outcome: str | None = None
    url: str | None = None


class SearchSentencesOutput(BaseModel):
    query: str
    sentences: list[Sentence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=SearchSentencesInput,
    output_model=SearchSentencesOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("stub", "legal"),
)
async def search_sentences(payload: SearchSentencesInput) -> SearchSentencesOutput:
    """Stub para buscador de sentencias (CGR, PJ). Devuelve lista vacía."""
    return SearchSentencesOutput(query=payload.name, sentences=[], citations=[])


# --------------------------------------------------------------- cross_vote_interest
class CrossVoteInput(BaseModel):
    legislator_name: str = Field(..., min_length=2, max_length=200)
    declared_assets: list[str] = Field(default_factory=list)


class VoteConflict(BaseModel):
    law_number: str | None = None
    law_title: str | None = None
    vote: str | None = None  # "favor" / "abstencion" / "contra"
    declared_asset: str | None = None
    overlap_reason: str | None = None
    confidence: float = 0.0


class CrossVoteOutput(BaseModel):
    legislator: str
    conflicts: list[VoteConflict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=CrossVoteInput,
    output_model=CrossVoteOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "congress"),
)
async def cross_vote_interest(payload: CrossVoteInput) -> CrossVoteOutput:
    """Stub que cruza votos del Congreso con intereses declarados."""
    return CrossVoteOutput(legislator=payload.legislator_name, conflicts=[], citations=[])


# --------------------------------------------------------------- query_sunarp_board
class SunarpBoardInput(BaseModel):
    ruc: str | None = None
    dni: str | None = None
    name: str | None = None


class BoardMember(BaseModel):
    dni: str | None = None
    name: str
    role: str | None = None  # "director", "gerente", "socio"
    company_ruc: str | None = None
    company_name: str | None = None


class SunarpBoardOutput(BaseModel):
    members: list[BoardMember] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=SunarpBoardInput,
    output_model=SunarpBoardOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("stub", "registry"),
)
async def query_sunarp_board(payload: SunarpBoardInput) -> SunarpBoardOutput:
    """Stub para directorios SUNARP. Devuelve lista vacía."""
    return SunarpBoardOutput(members=[], citations=[])


# --------------------------------------------------------------- expand_network
class ExpandNetworkInput(BaseModel):
    seed_dni: str | None = None
    seed_ruc: str | None = None
    max_depth: int = Field(2, ge=1, le=3)


class NetworkEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    depth: int
    source_url: str | None = None


class ExpandNetworkOutput(BaseModel):
    edges: list[NetworkEdge] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=ExpandNetworkInput,
    output_model=ExpandNetworkOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "graph"),
)
async def expand_network(payload: ExpandNetworkInput) -> ExpandNetworkOutput:
    """Stub para expansión de red de socios + familiares. Devuelve vacío."""
    return ExpandNetworkOutput(edges=[], citations=[])


# --------------------------------------------------------------- wayback_machine
class WaybackInput(BaseModel):
    url: str = Field(..., min_length=4, max_length=2000)
    limit: int = Field(10, ge=1, le=50)


class WaybackSnapshot(BaseModel):
    url: str
    timestamp: str  # ISO-8601
    archived_url: str
    status: int | None = None


class WaybackOutput(BaseModel):
    query_url: str
    snapshots: list[WaybackSnapshot] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=WaybackInput,
    output_model=WaybackOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "archive"),
)
async def wayback_machine(payload: WaybackInput) -> WaybackOutput:
    """Stub para Wayback Machine. Implementación real consulta CDX API."""
    return WaybackOutput(query_url=payload.url, snapshots=[], citations=[])


# --------------------------------------------------------------- search_twitter_archive
class TwitterArchiveInput(BaseModel):
    handle: str | None = Field(None, max_length=64)
    query: str | None = Field(None, max_length=300)
    limit: int = Field(20, ge=1, le=100)


class TwitterPost(BaseModel):
    handle: str | None = None
    posted_at: str | None = None  # ISO
    text: str | None = None
    url: str | None = None
    archived_url: str | None = None


class TwitterArchiveOutput(BaseModel):
    posts: list[TwitterPost] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    stub: bool = True


@ToolRegistry.register(
    country="pe",
    input_model=TwitterArchiveInput,
    output_model=TwitterArchiveOutput,
    cache_ttl=24 * 3600,
    tags=("stub", "social"),
)
async def search_twitter_archive(payload: TwitterArchiveInput) -> TwitterArchiveOutput:
    """Stub para archivo de Twitter/X. Devuelve lista vacía."""
    return TwitterArchiveOutput(posts=[], citations=[])


__all__ = [
    "find_dni_record",
    "find_ruc_record",
    "search_sentences",
    "cross_vote_interest",
    "query_sunarp_board",
    "expand_network",
    "wayback_machine",
    "search_twitter_archive",
    # Pydantic models exportados para tests:
    "FindDniInput",
    "FindDniOutput",
    "DniRecord",
    "FindRucInput",
    "FindRucOutput",
    "RucRecord",
    "SearchSentencesInput",
    "SearchSentencesOutput",
    "Sentence",
    "CrossVoteInput",
    "CrossVoteOutput",
    "VoteConflict",
    "SunarpBoardInput",
    "SunarpBoardOutput",
    "BoardMember",
    "ExpandNetworkInput",
    "ExpandNetworkOutput",
    "NetworkEdge",
    "WaybackInput",
    "WaybackOutput",
    "WaybackSnapshot",
    "TwitterArchiveInput",
    "TwitterArchiveOutput",
    "TwitterPost",
]
