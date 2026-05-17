from __future__ import annotations

from fastapi import HTTPException, Request, status

from src.auth.middleware import CurrentUser


def get_current_user(request: Request) -> CurrentUser | None:
    """Returns the authenticated user, or None if the caller is anonymous."""
    return getattr(request.state, "user", None)


def require_user(request: Request) -> CurrentUser:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user


__all__ = ["CurrentUser", "get_current_user", "require_user"]
