"""search_el_peruano.

Búsqueda en el diario oficial El Peruano (resoluciones, designaciones,
contratos directos). El sitio expone un buscador en ``https://busquedas.elperuano.pe``.

TTL: 7 días.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import ParserError
from ..registry import ToolRegistry
from ._common import Citation, Source

EL_PERUANO_BASE = "https://busquedas.elperuano.pe"


class ElPeruanoInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(25, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ElPeruanoResult(BaseModel):
    title: str
    norm_type: str | None = None  # "Resolución Ministerial", "Decreto Supremo", etc.
    issued_at: date | None = None
    snippet: str | None = None
    url: str


class ElPeruanoOutput(BaseModel):
    query: str
    results: list[ElPeruanoResult]
    citations: list[Citation]


@ToolRegistry.register(
    country="pe",
    input_model=ElPeruanoInput,
    output_model=ElPeruanoOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("legal", "press"),
)
async def search_el_peruano(payload: ElPeruanoInput) -> ElPeruanoOutput:
    """Busca normas legales y avisos en el diario oficial El Peruano."""
    params: dict[str, Any] = {"buscar": payload.query}
    if payload.date_from:
        params["desde"] = payload.date_from.strftime("%d/%m/%Y")
    if payload.date_to:
        params["hasta"] = payload.date_to.strftime("%d/%m/%Y")
    url = f"{EL_PERUANO_BASE}/NormasElperuano/Buscar?{urlencode(params)}"

    response = await http.get(url, tool="search_el_peruano", country="pe")
    http.raise_for_unexpected(response, tool="search_el_peruano", country="pe")
    results = _parse(response.text, payload.limit)

    citations = [
        Citation(
            text=(r.snippet or r.title)[:500],
            source=Source(url=r.url, source_type="el_peruano", title=r.title),
        )
        for r in results
    ]
    return ElPeruanoOutput(query=payload.query, results=results, citations=citations)


_NORM_RE = re.compile(
    r"(Resoluci[oó]n\s+\w+|Decreto\s+\w+|Ley\s+N[°º]?\s*\d+|Ordenanza\s+\w+)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _parse(html: str, limit: int) -> list[ElPeruanoResult]:
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError as exc:
        raise ParserError(
            "beautifulsoup4 required",
            tool="search_el_peruano",
            country="pe",
            cause=exc,
        ) from exc

    soup = BeautifulSoup(html, "html.parser")
    items: list[ElPeruanoResult] = []
    # El sitio renderiza resultados en <div class="resaltarurl"> + <h5> + <p>.
    for block in soup.select("div.resaltarurl, article.bsq-item, li.result"):
        title_node = block.find(["h5", "h4", "a"])
        if not title_node:
            continue
        title = title_node.get_text(strip=True)
        link_node = block.find("a", href=True)
        href = link_node["href"] if link_node else None
        if href and href.startswith("/"):
            href = EL_PERUANO_BASE + href
        snippet_node = block.find("p")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None

        norm_type = None
        norm_match = _NORM_RE.search(title or "")
        if norm_match:
            norm_type = norm_match.group(1)

        issued_at = None
        date_match = _DATE_RE.search((snippet or "") + " " + (title or ""))
        if date_match:
            try:
                issued_at = date(
                    int(date_match.group(3)),
                    int(date_match.group(2)),
                    int(date_match.group(1)),
                )
            except ValueError:
                issued_at = None

        items.append(
            ElPeruanoResult(
                title=title,
                norm_type=norm_type,
                issued_at=issued_at,
                snippet=snippet,
                url=href or EL_PERUANO_BASE,
            )
        )
        if len(items) >= limit:
            break
    return items


__all__ = ["search_el_peruano", "ElPeruanoInput", "ElPeruanoOutput", "ElPeruanoResult"]
