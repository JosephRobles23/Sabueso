"""Tool registry stub.

Replaced by S-04's full registry. This minimal version exposes the surface
BaseInvestigator needs: ToolDef + ToolRegistry.get_tools_for / register /
call(name, **args). When S-04 lands, drop-in replace this module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    country: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    handler: Callable[..., Awaitable[Any]]
    cache_ttl: int = 3600

    @property
    def qualified_name(self) -> str:
        return f"{self.country}:{self.name}"


class ToolRegistry:
    _tools: dict[str, ToolDef] = {}

    @classmethod
    def register(
        cls,
        country: str,
        *,
        name: str | None = None,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        cache_ttl: int = 3600,
    ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        def decorator(
            func: Callable[..., Awaitable[Any]],
        ) -> Callable[..., Awaitable[Any]]:
            tool = ToolDef(
                name=name or func.__name__,
                country=country,
                description=description or (func.__doc__ or "").strip(),
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                handler=func,
                cache_ttl=cache_ttl,
            )
            cls._tools[tool.qualified_name] = tool
            return func

        return decorator

    @classmethod
    def register_tool(cls, tool: ToolDef) -> None:
        cls._tools[tool.qualified_name] = tool

    @classmethod
    def get(cls, country: str, name: str) -> ToolDef | None:
        return cls._tools.get(f"{country}:{name}")

    @classmethod
    def get_tools_for(cls, country: str, allowed: list[str]) -> list[ToolDef]:
        return [
            cls._tools[f"{country}:{n}"]
            for n in allowed
            if f"{country}:{n}" in cls._tools
        ]

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()

    @classmethod
    def all(cls) -> list[ToolDef]:
        return list(cls._tools.values())
