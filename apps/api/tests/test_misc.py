from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.auth.current_user import get_current_user, require_user
from src.auth.middleware import CurrentUser
from src.services.rate_limit import allow_request
from src.settings import get_settings


def _fake_request(user: CurrentUser | None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("test", 0),
    }
    req = Request(scope)
    req.state.user = user
    return req


def test_require_user_raises_when_anonymous() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_user(_fake_request(None))
    assert exc_info.value.status_code == 401


def test_require_user_returns_user_when_present() -> None:
    from uuid import uuid4

    user = CurrentUser(id=uuid4(), email=None, claims={})
    assert require_user(_fake_request(user)) is user


def test_get_current_user_returns_none_for_anonymous() -> None:
    assert get_current_user(_fake_request(None)) is None


@pytest.mark.asyncio
async def test_rate_limit_hook_always_allows_for_now() -> None:
    from uuid import uuid4

    assert await allow_request(user_id=None) is True
    assert await allow_request(user_id=uuid4()) is True


def test_settings_cache_returns_same_instance() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
