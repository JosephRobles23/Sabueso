"""Typed errors for the tool layer.

Investigadores capturan estas excepciones para decidir si reintentar, descartar
la observación o cortar la cadena ReAct con un mensaje accionable.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base error para fallos invocando una tool.

    Atributos:
        tool: nombre de la tool (e.g. ``search_seace_contracts``)
        country: código país (``pe``/``cl``/...)
        cause: excepción original si la hay.
    """

    def __init__(
        self,
        message: str,
        *,
        tool: str | None = None,
        country: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.tool = tool
        self.country = country
        self.cause = cause

    def __str__(self) -> str:
        ctx = []
        if self.country:
            ctx.append(self.country)
        if self.tool:
            ctx.append(self.tool)
        prefix = f"[{':'.join(ctx)}] " if ctx else ""
        return prefix + super().__str__()


class RateLimitedError(ToolError):
    """La fuente respondió 429 o agotó el budget local del rate-limiter."""

    def __init__(
        self,
        message: str = "rate limited by upstream",
        *,
        retry_after: float | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class SourceUnavailableError(ToolError):
    """La fuente respondió 5xx después de agotar los retries o devolvió HTML
    de mantenimiento."""

    def __init__(
        self,
        message: str = "upstream source unavailable",
        *,
        status_code: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.status_code = status_code


class InvalidInputError(ToolError):
    """Argumentos no cumplen los validators Pydantic. Se usa cuando una tool
    recibe input ya filtrado por el subagente pero igual no valida (e.g. RUC
    de 10 dígitos)."""


class ParserError(ToolError):
    """La respuesta llegó pero no se pudo parsear (HTML cambió, JSON malformado,
    PDF escaneado sin OCR)."""
