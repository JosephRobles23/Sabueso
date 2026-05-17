"""Tool layer del worker.

Re-exporta el registry y los errores. Los módulos por país se importan
explícitamente vía ``ToolRegistry.load_pe_tools()`` en el startup del worker
para no acoplar el import del paquete a httpx/scrapling.
"""

from .cache import ToolCache, cached_tool_call, get_cache, set_cache
from .errors import (
    InvalidInputError,
    ParserError,
    RateLimitedError,
    SourceUnavailableError,
    ToolError,
)
from .rate_limit import RateLimiter, get_rate_limiter, set_rate_limiter
from .registry import (
    ToolDef,
    ToolRegistry,
    load_all_tools,
    load_cl_tools,
    load_mx_tools,
    load_pe_tools,
    load_sv_tools,
)

__all__ = [
    "InvalidInputError",
    "ParserError",
    "RateLimitedError",
    "RateLimiter",
    "SourceUnavailableError",
    "ToolCache",
    "ToolDef",
    "ToolError",
    "ToolRegistry",
    "cached_tool_call",
    "get_cache",
    "get_rate_limiter",
    "load_all_tools",
    "load_cl_tools",
    "load_mx_tools",
    "load_pe_tools",
    "load_sv_tools",
    "set_cache",
    "set_rate_limiter",
]
