"""query_sunarp_properties.

SUNARP no expone API pública para personas naturales — el flujo realista
durante hackathon es contra el portal SUNARP en Línea + reuso del corpus
``legalize-pe`` que ya tiene índices de bienes inmuebles publicados. Si está
disponible un endpoint privado vía API key (SABUESO_SUNARP_TOKEN) lo usamos
preferentemente.

TTL: 7 días.
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field, field_validator

from .. import http
from ..errors import ParserError, SourceUnavailableError
from ..registry import ToolRegistry
from ._common import Citation, Money, Source

SUNARP_PUBLIC = "https://www.sunarp.gob.pe"
SUNARP_API = "https://api.sunarp.gob.pe"  # placeholder; sólo si hay token.
DNI_RE = re.compile(r"^\d{8}$")


class SunarpInput(BaseModel):
    dni: str = Field(..., description="DNI de 8 dígitos del titular a consultar.")
    include_vehicles: bool = False

    @field_validator("dni")
    @classmethod
    def _dni(cls, v: str) -> str:
        v = v.strip()
        if not DNI_RE.match(v):
            raise ValueError("DNI debe tener 8 dígitos numéricos.")
        return v


class SunarpProperty(BaseModel):
    type: str  # "inmueble" / "vehiculo"
    partida: str | None = None
    descripcion: str | None = None
    ubicacion: str | None = None
    valor: Money | None = None
    fecha_inscripcion: str | None = None


class SunarpOutput(BaseModel):
    dni: str
    properties: list[SunarpProperty]
    citations: list[Citation]
    used_private_api: bool


@ToolRegistry.register(
    country="pe",
    input_model=SunarpInput,
    output_model=SunarpOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("registry", "properties"),
)
async def query_sunarp_properties(payload: SunarpInput) -> SunarpOutput:
    """Consulta titularidades inmobiliarias (y opcionalmente vehiculares) en
    SUNARP para el DNI dado. Prefiere API privada si hay token; cae al portal
    público con Scrapling si no.
    """
    token = os.environ.get("SABUESO_SUNARP_TOKEN")
    if token:
        return await _fetch_via_api(payload, token)
    return await _fetch_via_portal(payload)


async def _fetch_via_api(payload: SunarpInput, token: str) -> SunarpOutput:
    response = await http.get(
        f"{SUNARP_API}/v1/properties",
        params={"dni": payload.dni, "include_vehicles": int(payload.include_vehicles)},
        headers={"Authorization": f"Bearer {token}"},
        tool="query_sunarp_properties",
        country="pe",
    )
    http.raise_for_unexpected(response, tool="query_sunarp_properties", country="pe")
    try:
        data = response.json()
    except Exception as exc:
        raise ParserError(
            "SUNARP API returned non-JSON",
            tool="query_sunarp_properties",
            country="pe",
            cause=exc,
        ) from exc

    items = data.get("items") if isinstance(data, dict) else None
    properties: list[SunarpProperty] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        valor = item.get("valor")
        money = None
        if isinstance(valor, dict) and valor.get("amount") is not None:
            money = Money(
                amount=float(valor["amount"]),
                currency=valor.get("currency", "PEN"),
            )
        properties.append(
            SunarpProperty(
                type=item.get("type", "inmueble"),
                partida=item.get("partida"),
                descripcion=item.get("descripcion"),
                ubicacion=item.get("ubicacion"),
                valor=money,
                fecha_inscripcion=item.get("fecha_inscripcion"),
            )
        )

    source = Source(
        url=f"{SUNARP_API}/v1/properties?dni={payload.dni}",
        source_type="sunarp",
        title="SUNARP — consulta API privada",
    )
    citations = [
        Citation(
            text=f"{p.type} · {p.partida or 'sin partida'} · {p.ubicacion or 'ubicación n/d'}",
            source=source,
        )
        for p in properties
    ]
    return SunarpOutput(
        dni=payload.dni,
        properties=properties,
        citations=citations,
        used_private_api=True,
    )


async def _fetch_via_portal(payload: SunarpInput) -> SunarpOutput:
    """El portal público no soporta búsqueda por DNI sin captcha. Devolvemos
    output vacío con citation apuntando al portal (que el subagente puede
    documentar como límite)."""
    portal = f"{SUNARP_PUBLIC}/consulta-personas-juridicas"
    try:
        await http.get(portal, tool="query_sunarp_properties", country="pe")
    except SourceUnavailableError:
        # El portal cae seguido; no es fatal, sólo registramos.
        pass

    citations = [
        Citation(
            text=(
                f"Consulta directa por DNI {payload.dni} no disponible vía portal "
                "público de SUNARP (requiere captcha o cuenta SUNARP en Línea)."
            ),
            source=Source(url=portal, source_type="sunarp", title="SUNARP Portal"),
        )
    ]
    return SunarpOutput(
        dni=payload.dni,
        properties=[],
        citations=citations,
        used_private_api=False,
    )


__all__ = ["query_sunarp_properties", "SunarpInput", "SunarpOutput", "SunarpProperty"]
