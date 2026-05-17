"""search_manolo.

Manolo.pe agrega visitas a entidades públicas (Palacio de Gobierno, ministerios,
Congreso). Es scrapeo HTML — los selectors cambian con cierta frecuencia. Por
eso usamos Scrapling en modo stealth con fallback a httpx para no fallar
catastróficamente cuando Scrapling no está instalada (CI minimal).

TTL: 24h.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import ParserError, SourceUnavailableError
from ..registry import ToolRegistry
from ._common import Citation, Source

MANOLO_BASE = "https://www.manolo.pe"
MANOLO_HOST = "www.manolo.pe"
DNI_RE = re.compile(r"^\d{8}$")


class ManoloInput(BaseModel):
    query: str = Field(..., min_length=2, description="DNI (8 dígitos) o nombre.")
    limit: int = Field(50, ge=1, le=200)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ManoloVisit(BaseModel):
    visitor: str | None = None
    dni: str | None = None
    entity: str | None = None
    host: str | None = None
    reason: str | None = None
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    source_url: str | None = None


class ManoloOutput(BaseModel):
    query: str
    visits: list[ManoloVisit]
    citations: list[Citation]


@ToolRegistry.register(
    country="pe",
    input_model=ManoloInput,
    output_model=ManoloOutput,
    cache_ttl=24 * 3600,
    tags=("visits", "transparency"),
)
async def search_manolo(payload: ManoloInput) -> ManoloOutput:
    """Busca registros de visitas oficiales en Manolo.pe por DNI o nombre.

    El resultado incluye visitas estructuradas + citations con extracts ≤500
    chars para alimentar claims/sources.
    """
    search_path = "/buscar"
    params = {"q": payload.query, "is_dni": int(bool(DNI_RE.match(payload.query)))}

    html = await _fetch_html(f"{MANOLO_BASE}{search_path}", params=params)
    visits = _parse_visits(html, limit=payload.limit, default_url=f"{MANOLO_BASE}{search_path}")

    citations = [_visit_to_citation(v) for v in visits if v.visitor or v.entity]
    return ManoloOutput(
        query=payload.query,
        visits=visits,
        citations=citations,
    )


async def _fetch_html(url: str, params: dict[str, Any]) -> str:
    """Intenta Scrapling stealth; si no está disponible cae a httpx."""
    try:
        from scrapling.fetchers import StealthyFetcher  # noqa: PLC0415

        fetcher = StealthyFetcher(auto_match=False)
        # build URL with params manually so Scrapling lo trata como GET simple.
        full = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        page = await fetcher.async_fetch(full, headless=True, network_idle=True)
        if page.status >= 500:
            raise SourceUnavailableError(
                f"manolo returned {page.status}",
                tool="search_manolo",
                country="pe",
                status_code=page.status,
            )
        return page.html_content
    except ImportError:
        pass
    except SourceUnavailableError:
        raise
    except Exception:
        # cualquier issue de Scrapling: caemos a httpx
        pass

    response = await http.get(
        url, params=params, tool="search_manolo", country="pe"
    )
    http.raise_for_unexpected(response, tool="search_manolo", country="pe")
    return response.text


def _parse_visits(html: str, *, limit: int, default_url: str) -> list[ManoloVisit]:
    """Parser HTML tolerante. Los selectors de Manolo cambian seguido, así que
    extraemos por heurística (tabla con headers en español)."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError as exc:
        raise ParserError(
            "beautifulsoup4 not installed but required for manolo parsing",
            tool="search_manolo",
            country="pe",
            cause=exc,
        ) from exc

    soup = BeautifulSoup(html, "html.parser")
    visits: list[ManoloVisit] = []
    for table in soup.find_all("table"):
        headers = [_norm(th.get_text()) for th in table.find_all("th")]
        if not headers:
            continue
        col = {h: i for i, h in enumerate(headers)}
        get = lambda cells, key: (  # noqa: E731
            cells[col[key]].get_text(strip=True) if key in col and col[key] < len(cells) else None
        )

        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            visitor = get(cells, "visitante") or get(cells, "nombre")
            entity = get(cells, "entidad") or get(cells, "institucion")
            host = get(cells, "anfitrion") or get(cells, "funcionario")
            reason = get(cells, "motivo") or get(cells, "razon")
            entry = _parse_dt(get(cells, "fecha") or get(cells, "ingreso"))
            exit_ = _parse_dt(get(cells, "salida"))
            dni = get(cells, "dni")
            if not any([visitor, entity, host, reason]):
                continue
            visits.append(
                ManoloVisit(
                    visitor=visitor,
                    dni=dni,
                    entity=entity,
                    host=host,
                    reason=reason,
                    entry_at=entry,
                    exit_at=exit_,
                    source_url=default_url,
                )
            )
            if len(visits) >= limit:
                return visits
    return visits


def _norm(s: str) -> str:
    import unicodedata  # noqa: PLC0415

    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _visit_to_citation(v: ManoloVisit) -> Citation:
    parts = [p for p in [v.visitor, "→", v.entity, v.reason] if p]
    text = " ".join(str(p) for p in parts)[:500]
    return Citation(
        text=text,
        source=Source(
            url=v.source_url or f"{MANOLO_BASE}/buscar",
            source_type="manolo",
            title="Manolo.pe — visitas oficiales",
        ),
        extra={"host": v.host, "entry_at": v.entry_at.isoformat() if v.entry_at else None},
    )


__all__ = ["search_manolo", "ManoloInput", "ManoloOutput", "ManoloVisit"]
