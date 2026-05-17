"""search_news_archive.

Búsqueda priorizada en archivos de prensa peruana: IDL Reporteros, OjoPúblico,
Convoca y Wayback como fallback histórico. La estrategia es invocar cada fuente
en paralelo, deduplicar por URL y rankear por prioridad de fuente + recencia.

TTL: 1 día (las publicaciones se actualizan diariamente).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import SourceUnavailableError
from ..registry import ToolRegistry
from ._common import Citation, Source

SOURCE_PRIORITY = {
    "idl-reporteros.pe": 1,
    "ojo-publico.com": 1,
    "convoca.pe": 1,
    "elcomercio.pe": 2,
    "larepublica.pe": 2,
    "web.archive.org": 3,
}


class NewsInput(BaseModel):
    entity_name: str = Field(..., min_length=2, max_length=200)
    limit: int = Field(20, ge=1, le=100)

    @field_validator("entity_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class NewsArticle(BaseModel):
    title: str
    url: str
    source_domain: str
    snippet: str | None = None
    published_at: datetime | None = None
    priority: int  # 1..3, menor = más prioritario


class NewsOutput(BaseModel):
    query: str
    articles: list[NewsArticle]
    citations: list[Citation]
    sources_failed: list[str]


@ToolRegistry.register(
    country="pe",
    input_model=NewsInput,
    output_model=NewsOutput,
    cache_ttl=24 * 3600,
    tags=("press", "archive"),
)
async def search_news_archive(payload: NewsInput) -> NewsOutput:
    """Busca menciones del entity_name en archivos de prensa de investigación
    peruana (IDL/OjoPúblico/Convoca) + Wayback como fallback histórico.
    """
    tasks = [
        _search_idl(payload.entity_name),
        _search_ojopublico(payload.entity_name),
        _search_convoca(payload.entity_name),
        _search_wayback(payload.entity_name),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles: list[NewsArticle] = []
    failed: list[str] = []
    source_names = ["idl-reporteros.pe", "ojo-publico.com", "convoca.pe", "web.archive.org"]
    for name, r in zip(source_names, results, strict=True):
        if isinstance(r, BaseException):
            failed.append(name)
            continue
        articles.extend(r)

    # Dedup por URL y orden por (priority asc, published_at desc).
    seen: set[str] = set()
    unique: list[NewsArticle] = []
    for art in articles:
        if art.url in seen:
            continue
        seen.add(art.url)
        unique.append(art)
    unique.sort(key=lambda a: (a.priority, -(a.published_at.timestamp() if a.published_at else 0)))
    unique = unique[: payload.limit]

    citations = [
        Citation(
            text=((a.snippet or a.title) or "")[:500],
            source=Source(url=a.url, source_type="press", title=a.title),
        )
        for a in unique
    ]
    return NewsOutput(
        query=payload.entity_name,
        articles=unique,
        citations=citations,
        sources_failed=failed,
    )


async def _search_idl(name: str) -> list[NewsArticle]:
    return await _generic_search(
        domain="idl-reporteros.pe",
        url=f"https://idl-reporteros.pe/?s={quote_plus(name)}",
        priority=1,
    )


async def _search_ojopublico(name: str) -> list[NewsArticle]:
    return await _generic_search(
        domain="ojo-publico.com",
        url=f"https://ojo-publico.com/buscar?s={quote_plus(name)}",
        priority=1,
    )


async def _search_convoca(name: str) -> list[NewsArticle]:
    return await _generic_search(
        domain="convoca.pe",
        url=f"https://convoca.pe/?s={quote_plus(name)}",
        priority=1,
    )


async def _search_wayback(name: str) -> list[NewsArticle]:
    """Wayback CDX API: archivos de URLs que contienen el nombre."""
    url = (
        "https://web.archive.org/cdx/search/cdx?"
        f"url=*{quote_plus(name)}*&output=json&limit=15&fl=timestamp,original"
    )
    try:
        response = await http.get(url, tool="search_news_archive", country="pe")
    except SourceUnavailableError:
        return []
    if response.status_code != 200:
        return []
    try:
        data = response.json()
    except Exception:
        return []
    if not isinstance(data, list) or len(data) < 2:
        return []

    articles: list[NewsArticle] = []
    for row in data[1:]:
        if not isinstance(row, list) or len(row) < 2:
            continue
        ts, original = row[0], row[1]
        try:
            published = datetime.strptime(ts, "%Y%m%d%H%M%S")
        except (ValueError, TypeError):
            published = None
        articles.append(
            NewsArticle(
                title=original[:200],
                url=f"https://web.archive.org/web/{ts}/{original}",
                source_domain="web.archive.org",
                snippet=None,
                published_at=published,
                priority=3,
            )
        )
    return articles


async def _generic_search(*, domain: str, url: str, priority: int) -> list[NewsArticle]:
    try:
        response = await http.get(url, tool="search_news_archive", country="pe")
    except SourceUnavailableError:
        return []
    if response.status_code != 200:
        return []
    return _parse_html_results(
        html=response.text,
        domain=domain,
        priority=priority,
        fallback_url=url,
    )


def _parse_html_results(
    *, html: str, domain: str, priority: int, fallback_url: str
) -> list[NewsArticle]:
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out: list[NewsArticle] = []
    for art in soup.select("article, div.post, li.search-result, h2 a, h3 a"):
        title_node = (
            art.find("a", href=True)
            if art.name in ("article", "div", "li")
            else art
        )
        if not title_node or not getattr(title_node, "get", None):
            continue
        href = title_node.get("href")
        if not href:
            continue
        if href.startswith("/"):
            href = f"https://{domain}{href}"
        title = title_node.get_text(strip=True)
        if not title:
            continue
        snippet_node = art.find("p") if hasattr(art, "find") else None
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
        out.append(
            NewsArticle(
                title=title[:200],
                url=href,
                source_domain=domain,
                snippet=snippet,
                published_at=None,
                priority=priority,
            )
        )
    if out:
        return out[:25]
    return [
        NewsArticle(
            title="Sin resultados parseables — verificar manualmente",
            url=fallback_url,
            source_domain=domain,
            snippet=None,
            published_at=None,
            priority=priority,
        )
    ]


__all__ = ["search_news_archive", "NewsInput", "NewsOutput", "NewsArticle"]
