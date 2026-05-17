"""search_seace_contracts.

OECE / SEACE expone un endpoint OCDS-style en
``https://contratacionesabiertas.osce.gob.pe``. Agregamos por RUC y rango de
años, paginamos con ``offset/limit``.

TTL: 24h (las publicaciones de SEACE se actualizan diariamente).

Rate limit: el host está más conservador (1 req/s) — lo seteamos en ``apply_pe_rate_limits``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import ParserError
from ..registry import ToolRegistry
from ._common import Money, Source

SEACE_BASE = "https://contratacionesabiertas.osce.gob.pe"
SEACE_HOST = "contratacionesabiertas.osce.gob.pe"
PAGE_SIZE = 100
MAX_PAGES = 25  # hard ceiling: 2500 contratos por RUC ya es outlier.


class SeaceInput(BaseModel):
    ruc: str = Field(..., description="RUC del proveedor o entidad contratante (11 dígitos).")
    year_from: int = Field(2014, ge=2000, le=2030)
    year_to: int = Field(2026, ge=2000, le=2030)

    @field_validator("ruc")
    @classmethod
    def _ruc_format(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 11:
            raise ValueError("RUC debe tener 11 dígitos numéricos.")
        return v


class SeaceContract(BaseModel):
    ocid: str | None = None
    title: str | None = None
    buyer: str | None = None
    supplier: str | None = None
    award_date: str | None = None
    value: Money | None = None
    url: str | None = None


class SeaceOutput(BaseModel):
    ruc: str
    contracts: list[SeaceContract]
    total_amount: Money
    pages_fetched: int
    sources: list[Source]


@ToolRegistry.register(
    country="pe",
    input_model=SeaceInput,
    output_model=SeaceOutput,
    cache_ttl=24 * 3600,
    tags=("contracts", "ocds"),
)
async def search_seace_contracts(payload: SeaceInput) -> SeaceOutput:
    """Busca contratos del RUC dado en SEACE/OECE (OCDS).

    Agrega ``contracts`` y ``total_amount``. Pagina con offset/limit hasta
    ``MAX_PAGES`` o fin de resultados.
    """
    contracts: list[SeaceContract] = []
    total = 0.0
    pages = 0

    for page in range(MAX_PAGES):
        offset = page * PAGE_SIZE
        params = {
            "ruc": payload.ruc,
            "year_from": payload.year_from,
            "year_to": payload.year_to,
            "limit": PAGE_SIZE,
            "offset": offset,
        }
        response = await http.get(
            f"{SEACE_BASE}/api/v1/releases",
            params=params,
            tool="search_seace_contracts",
            country="pe",
        )
        http.raise_for_unexpected(response, tool="search_seace_contracts", country="pe")
        try:
            data = response.json()
        except Exception as exc:
            raise ParserError(
                "SEACE returned non-JSON payload",
                tool="search_seace_contracts",
                country="pe",
                cause=exc,
            ) from exc

        page_contracts, page_total = _parse_releases(data)
        contracts.extend(page_contracts)
        total += page_total
        pages = page + 1

        # OCDS estándar usa "pagination.next" o array vacío. Tolerante.
        if len(page_contracts) < PAGE_SIZE:
            break

    sources = [
        Source(
            url=f"{SEACE_BASE}/buscador-de-contrataciones?ruc={payload.ruc}",
            source_type="seace",
            title=f"SEACE — contrataciones RUC {payload.ruc}",
        )
    ]
    return SeaceOutput(
        ruc=payload.ruc,
        contracts=contracts,
        total_amount=Money(amount=round(total, 2), currency="PEN"),
        pages_fetched=pages,
        sources=sources,
    )


def _parse_releases(data: Any) -> tuple[list[SeaceContract], float]:
    """OCDS release payload → (contratos, suma). Tolerante a variaciones."""
    releases = []
    if isinstance(data, dict):
        releases = data.get("releases") or data.get("data") or data.get("results") or []
    elif isinstance(data, list):
        releases = data

    contracts: list[SeaceContract] = []
    total = 0.0
    for rel in releases:
        if not isinstance(rel, dict):
            continue
        ocid = rel.get("ocid") or rel.get("id")
        tender = rel.get("tender") or {}
        buyer_obj = rel.get("buyer") or tender.get("procuringEntity") or {}
        awards = rel.get("awards") or []

        for award in awards:
            if not isinstance(award, dict):
                continue
            value_obj = award.get("value") or {}
            amount = float(value_obj.get("amount") or 0)
            currency = value_obj.get("currency") or "PEN"
            suppliers = award.get("suppliers") or []
            supplier_name = (
                suppliers[0].get("name") if suppliers and isinstance(suppliers[0], dict) else None
            )
            contracts.append(
                SeaceContract(
                    ocid=ocid,
                    title=tender.get("title") or award.get("title"),
                    buyer=buyer_obj.get("name"),
                    supplier=supplier_name,
                    award_date=award.get("date"),
                    value=Money(amount=amount, currency=currency) if amount else None,
                    url=rel.get("url"),
                )
            )
            total += amount
    return contracts, total


__all__ = ["search_seace_contracts", "SeaceInput", "SeaceOutput", "SeaceContract"]
