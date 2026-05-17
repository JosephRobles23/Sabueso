"""SSE machinery: LISTEN/NOTIFY → async queue → EventSourceResponse (S-08)."""

from src.sse.events import (
    TERMINAL_EVENT_TYPES,
    EventType,
    StreamedEvent,
    sanitize_channel,
)
from src.sse.listener import (
    InvestigationListener,
    PoolExhaustedError,
)
from src.sse.stream import event_stream

__all__ = [
    "EventType",
    "InvestigationListener",
    "PoolExhaustedError",
    "StreamedEvent",
    "TERMINAL_EVENT_TYPES",
    "event_stream",
    "sanitize_channel",
]
