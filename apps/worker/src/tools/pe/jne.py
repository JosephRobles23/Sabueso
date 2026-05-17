"""fetch_jne_hoja_vida.

JNE publica hojas de vida en PDF en
``https://plataformaelectoral.jne.gob.pe/HojaVida/...``. Bajamos el PDF, lo
extraemos con PyMuPDF (fallback heurístico si pages vienen escaneadas), subimos
el original a GCS para auditoría y devolvemos campos estructurados.

TTL: 30 días (las hojas de vida son inmutables una vez publicadas).
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import ParserError, ToolError
from ..registry import ToolRegistry
from ._common import Citation, Money, Source

JNE_BASE = "https://plataformaelectoral.jne.gob.pe"


class JneInput(BaseModel):
    candidate_id: str = Field(..., min_length=1, max_length=64)
    pdf_url: str | None = Field(
        None,
        description=(
            "Si conocés el URL directo del PDF, lo bajamos sin pasar por el "
            "buscador. Si no, construimos un URL heurístico."
        ),
    )

    @field_validator("candidate_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class JneEducation(BaseModel):
    level: str | None = None
    institution: str | None = None
    year: int | None = None


class JneSentence(BaseModel):
    case: str | None = None
    crime: str | None = None
    year: int | None = None
    sentence: str | None = None


class JneOutput(BaseModel):
    candidate_id: str
    full_name: str | None = None
    dni: str | None = None
    party: str | None = None
    office_seeking: str | None = None
    education: list[JneEducation]
    properties_declared: list[str]
    income_declared: Money | None = None
    sentences: list[JneSentence]
    raw_text: str = Field(..., max_length=200_000)
    gcs_uri: str | None = None
    pdf_url: str
    sources: list[Source]
    citations: list[Citation]


@ToolRegistry.register(
    country="pe",
    input_model=JneInput,
    output_model=JneOutput,
    cache_ttl=30 * 24 * 3600,
    tags=("electoral", "pdf"),
)
async def fetch_jne_hoja_vida(payload: JneInput) -> JneOutput:
    """Descarga la hoja de vida JNE del candidato, extrae texto con PyMuPDF
    y sube el PDF original a GCS. Retorna campos estructurados + raw_text para
    que el subagente pueda buscar adicionalmente.
    """
    pdf_url = payload.pdf_url or _build_pdf_url(payload.candidate_id)
    response = await http.get(pdf_url, tool="fetch_jne_hoja_vida", country="pe")
    http.raise_for_unexpected(response, tool="fetch_jne_hoja_vida", country="pe")
    pdf_bytes = response.content
    if not pdf_bytes.startswith(b"%PDF"):
        raise ParserError(
            "JNE response is not a PDF",
            tool="fetch_jne_hoja_vida",
            country="pe",
        )

    text = _extract_text(pdf_bytes)
    structured = _parse_hoja_vida(text)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    gcs_uri = await _upload_to_gcs(pdf_bytes, payload.candidate_id, sha)

    source = Source(
        url=pdf_url,
        source_type="jne",
        title=f"JNE Hoja de Vida — candidato {payload.candidate_id}",
        content_hash=sha,
        content_storage=gcs_uri,
    )
    citations = _build_citations(text, source)

    return JneOutput(
        candidate_id=payload.candidate_id,
        full_name=structured["full_name"],
        dni=structured["dni"],
        party=structured["party"],
        office_seeking=structured["office_seeking"],
        education=structured["education"],
        properties_declared=structured["properties_declared"],
        income_declared=structured["income_declared"],
        sentences=structured["sentences"],
        raw_text=text[:200_000],
        gcs_uri=gcs_uri,
        pdf_url=pdf_url,
        sources=[source],
        citations=citations,
    )


def _build_pdf_url(candidate_id: str) -> str:
    # Patrón observado en el portal JNE 2021/2026.
    return f"{JNE_BASE}/HojaVidaCandidato/Descargar/{candidate_id}"


def _extract_text(pdf_bytes: bytes) -> str:
    try:
        import fitz  # type: ignore[import-not-found]  # pymupdf  # noqa: PLC0415
    except ImportError as exc:
        raise ParserError(
            "pymupdf not installed",
            tool="fetch_jne_hoja_vida",
            country="pe",
            cause=exc,
        ) from exc

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            chunks = [page.get_text("text") for page in doc]
    except Exception as exc:
        raise ParserError(
            f"failed to open PDF with PyMuPDF: {exc}",
            tool="fetch_jne_hoja_vida",
            country="pe",
            cause=exc,
        ) from exc

    text = "\n".join(chunks)
    if len(text.strip()) < 100:
        # PDF probablemente escaneado: el caller podría correr Tika/OCR.
        raise ParserError(
            "JNE PDF appears scanned (text < 100 chars); OCR fallback needed",
            tool="fetch_jne_hoja_vida",
            country="pe",
        )
    return text


_NAME_RE = re.compile(
    r"(?:Nombres? y Apellidos?|Apellidos y Nombres?)\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)
_DNI_RE = re.compile(r"DNI[\s:N°#-]*([0-9]{8})", re.IGNORECASE)
_PARTY_RE = re.compile(r"(?:Organizaci[oó]n pol[ií]tica|Partido)\s*[:\-]?\s*(.+)", re.IGNORECASE)
_OFFICE_RE = re.compile(r"(?:Cargo|Postula a|Postulaci[oó]n)\s*[:\-]?\s*(.+)", re.IGNORECASE)
_INCOME_RE = re.compile(r"(?:Ingreso anual|Ingresos)\s*[:\-]?\s*S\/\.?\s*([\d,.]+)", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?:Sentencia|Condena).{0,200}?(\d{4})", re.IGNORECASE | re.DOTALL)


def _parse_hoja_vida(text: str) -> dict[str, Any]:
    full_name = _first_group(_NAME_RE, text)
    dni = _first_group(_DNI_RE, text)
    party = _first_group(_PARTY_RE, text)
    office = _first_group(_OFFICE_RE, text)

    income: Money | None = None
    m = _INCOME_RE.search(text)
    if m:
        try:
            amount = float(m.group(1).replace(",", ""))
            income = Money(amount=amount, currency="PEN")
        except ValueError:
            income = None

    sentences: list[JneSentence] = []
    for sm in _SENTENCE_RE.finditer(text):
        try:
            year = int(sm.group(1))
        except (TypeError, ValueError):
            year = None
        sentences.append(JneSentence(year=year, case=sm.group(0).strip()[:200]))

    # Propiedades: heurística — líneas que mencionan "bien inmueble" o "predio".
    properties = []
    for line in text.splitlines():
        low = line.lower()
        if "bien inmueble" in low or "predio" in low or "propiedad" in low:
            properties.append(line.strip()[:300])
        if len(properties) >= 30:
            break

    # Educación: bloque entre "Educación" y la siguiente sección.
    education: list[JneEducation] = []
    edu_block = _section(text, "Educaci")
    if edu_block:
        for line in edu_block.splitlines():
            line = line.strip()
            if not line or len(line) < 5:
                continue
            year_match = re.search(r"(\d{4})", line)
            year = int(year_match.group(1)) if year_match else None
            education.append(JneEducation(level=None, institution=line[:200], year=year))
            if len(education) >= 20:
                break

    return {
        "full_name": full_name,
        "dni": dni,
        "party": party,
        "office_seeking": office,
        "education": education,
        "properties_declared": properties,
        "income_declared": income,
        "sentences": sentences,
    }


def _first_group(regex: re.Pattern[str], text: str) -> str | None:
    m = regex.search(text)
    if not m:
        return None
    return m.group(1).strip()[:200]


def _section(text: str, header_keyword: str) -> str | None:
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        if header_keyword.lower() in line.lower() and not capturing:
            capturing = True
            continue
        if capturing:
            if re.match(r"^\s*[A-ZÁÉÍÓÚÑ ]{6,}\s*$", line):
                # nueva sección en mayúsculas → parar
                break
            out.append(line)
            if len(out) > 50:
                break
    return "\n".join(out) if out else None


def _build_citations(text: str, source: Source) -> list[Citation]:
    snippets = []
    for keyword in ("Sentencia", "Bien inmueble", "Ingreso"):
        idx = text.lower().find(keyword.lower())
        if idx < 0:
            continue
        snippet = text[idx : idx + 400].replace("\n", " ").strip()
        snippets.append(Citation(text=snippet[:500], source=source))
    if not snippets:
        snippets.append(Citation(text=text[:500], source=source))
    return snippets


async def _upload_to_gcs(pdf_bytes: bytes, candidate_id: str, sha: str) -> str | None:
    bucket_name = os.environ.get("SABUESO_GCS_BUCKET")
    if not bucket_name:
        return None
    try:
        from google.cloud import storage  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError:
        return None
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"jne/{candidate_id}/{sha}.pdf")
        blob.upload_from_string(pdf_bytes, content_type="application/pdf")
        return f"gs://{bucket_name}/jne/{candidate_id}/{sha}.pdf"
    except Exception as exc:
        # No-fatal: el PDF está en memoria y el sha está en el output.
        raise ToolError(
            f"GCS upload failed (continuing): {exc}",
            tool="fetch_jne_hoja_vida",
            country="pe",
            cause=exc,
        ) from exc


__all__ = ["fetch_jne_hoja_vida", "JneInput", "JneOutput", "JneSentence", "JneEducation"]
