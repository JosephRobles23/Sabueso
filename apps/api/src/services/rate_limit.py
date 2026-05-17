from __future__ import annotations

from uuid import UUID


async def allow_request(*, user_id: UUID | None) -> bool:
    """Rate-limit hook. S-20 wires Vercel KV; until then we always allow.

    Returning a bool (instead of raising) keeps the door open for tests to monkey-patch
    a deny path without changing call sites.
    """
    _ = user_id  # explicit "intentionally unused for now"
    return True
