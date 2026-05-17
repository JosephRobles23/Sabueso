"""ToolRegistry: namespacing por país + MCP-ready manifest.

Cada tool se declara así::

    class SearchSeaceInput(BaseModel):
        ruc: str = Field(..., pattern=r"^\\d{11}$")
        year_from: int = 2014
        year_to: int = 2026

    class SearchSeaceOutput(BaseModel):
        contracts: list[Contract]
        total_amount: float

    @ToolRegistry.register(
        country="pe",
        input_model=SearchSeaceInput,
        output_model=SearchSeaceOutput,
        cache_ttl=24 * 3600,
    )
    async def search_seace_contracts(payload: SearchSeaceInput) -> SearchSeaceOutput:
        \"\"\"docstring → tool description en el manifest.\"\"\"
        ...

El registry:
- valida input antes de invocar al handler
- envuelve la llamada con ``cached_tool_call``
- expone ``call(country, name, args)`` para el orchestrator
- expone ``export_as_mcp()`` con el manifest JSON-Schema válido
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from .cache import ToolCache, cached_tool_call, get_cache
from .errors import InvalidInputError, ToolError

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

Handler = Callable[[Any], Awaitable[BaseModel]]


@dataclass
class ToolDef(Generic[InputT, OutputT]):  # noqa: UP046  # dataclass + PEP 695 conflict
    """Definición declarativa de una tool. Inmutable después de register."""

    name: str
    country: str
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]
    handler: Handler
    cache_ttl: int = 3600
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified_name(self) -> str:
        return f"{self.country}:{self.name}"

    @property
    def input_schema(self) -> dict[str, Any]:
        return _sanitize_schema(self.input_model.model_json_schema())

    @property
    def output_schema(self) -> dict[str, Any]:
        return _sanitize_schema(self.output_model.model_json_schema())

    def to_mcp(self) -> dict[str, Any]:
        """Forma compatible con MCP Tool object spec.

        Spec mínimo de MCP::

            {
              "name": str,
              "description": str,
              "inputSchema": <JSON Schema object>
            }

        Agregamos ``outputSchema`` (extensión bien soportada) y metadata
        ``x-sabueso`` para country/cache_ttl.
        """
        return {
            "name": self.name,
            "description": (self.description or "").strip(),
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "x-sabueso": {
                "country": self.country,
                "cache_ttl_seconds": self.cache_ttl,
                "tags": list(self.tags),
            },
        }


class ToolRegistry:
    """Registry global de tools. Las tools se registran al importar el módulo."""

    _tools: dict[str, ToolDef[Any, Any]] = {}

    @classmethod
    def register(
        cls,
        *,
        country: str,
        input_model: type[InputT],
        output_model: type[OutputT],
        cache_ttl: int = 3600,
        tags: tuple[str, ...] = (),
    ) -> Callable[[Handler], Handler]:
        """Decorator. ``handler`` recibe una instancia de ``input_model``.

        El nombre de la tool es ``func.__name__``. La descripción es
        ``func.__doc__`` (primer párrafo).
        """

        def decorator(func: Handler) -> Handler:
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"tool handler {func.__name__} must be async")
            description = inspect.getdoc(func) or func.__name__
            tool = ToolDef(
                name=func.__name__,
                country=country,
                description=description,
                input_model=input_model,
                output_model=output_model,
                handler=func,
                cache_ttl=cache_ttl,
                tags=tags,
            )
            cls._tools[tool.qualified_name] = tool
            return func

        return decorator

    @classmethod
    def get(cls, country: str, name: str) -> ToolDef[Any, Any]:
        key = f"{country}:{name}"
        if key not in cls._tools:
            raise KeyError(f"tool not registered: {key}")
        return cls._tools[key]

    @classmethod
    def get_tools_for(
        cls, country: str, allowed: list[str] | None = None
    ) -> list[ToolDef[Any, Any]]:
        """Retorna tools del país pedido. Si ``allowed`` se pasa, filtra por
        nombre (no fully-qualified)."""
        country_tools = [t for t in cls._tools.values() if t.country == country]
        if allowed is None:
            return country_tools
        allowed_set = set(allowed)
        return [t for t in country_tools if t.name in allowed_set]

    @classmethod
    def export_as_mcp(cls, country: str | None = None) -> dict[str, Any]:
        """Manifest MCP-compatible. Si ``country`` es None exporta todos."""
        if country is None:
            tools = list(cls._tools.values())
        else:
            tools = cls.get_tools_for(country)
        return {
            "schemaVersion": "2024-11-05",
            "serverInfo": {
                "name": "sabueso-tools",
                "version": "0.1.0",
            },
            "tools": [t.to_mcp() for t in tools],
        }

    @classmethod
    def all(cls) -> list[ToolDef[Any, Any]]:
        return list(cls._tools.values())

    @classmethod
    async def call(
        cls,
        *,
        country: str,
        name: str,
        args: dict[str, Any],
        cache: ToolCache | None = None,
    ) -> BaseModel:
        """Invoca la tool con cache. Punto de entrada del orchestrator."""
        tool = cls.get(country, name)
        try:
            payload = tool.input_model.model_validate(args)
        except Exception as exc:
            raise InvalidInputError(
                f"invalid input: {exc}",
                tool=tool.name,
                country=tool.country,
                cause=exc,
            ) from exc

        cache_args = payload.model_dump(mode="json")

        async def _bound_handler(**_: Any) -> BaseModel:
            return await tool.handler(payload)

        try:
            return await cached_tool_call(
                country=tool.country,
                tool_name=tool.name,
                args=cache_args,
                ttl_seconds=tool.cache_ttl,
                output_model=tool.output_model,
                handler=_bound_handler,
                cache=cache or get_cache(),
            )
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"unhandled error: {exc}",
                tool=tool.name,
                country=tool.country,
                cause=exc,
            ) from exc

    @classmethod
    def _reset(cls) -> None:
        """Test helper. No usar en runtime."""
        cls._tools.clear()


def _sanitize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Limpia campos no estándar que Pydantic agrega y MCP no espera."""
    cleaned = dict(schema)
    # Pydantic agrega "title" en cada nivel; lo dejamos arriba pero limpiamos
    # el resto para que el manifest se vea ordenado.
    cleaned.pop("$defs", None) if "$defs" not in cleaned else None
    return cleaned


def load_pe_tools() -> None:
    """Importa los módulos de tools PE para que los decoradores corran.

    Idempotente: importar dos veces no duplica entries (cada tool se registra
    bajo su qualified_name único).
    """
    from .pe import (  # noqa: F401, PLC0415
        el_peruano,
        jne,
        legalize,
        manolo,
        news,
        relatives,
        seace,
        sunarp,
    )
