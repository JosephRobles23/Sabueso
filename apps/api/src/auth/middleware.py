from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.auth.jwks import JWKSCache

log = structlog.get_logger(__name__)


class CurrentUser:
    """Lightweight identity attached to request.state when JWT validates."""

    __slots__ = ("id", "email", "claims")

    def __init__(self, *, id: UUID, email: str | None, claims: dict[str, Any]) -> None:
        self.id = id
        self.email = email
        self.claims = claims


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Supabase JWT when present; allow anonymous otherwise.

    - No `Authorization` header → request.state.user = None (anonymous, rate-limited by IP).
    - `Authorization: Bearer <jwt>` + JWKS configured + valid → state.user = CurrentUser.
    - `Authorization: Bearer <jwt>` + JWKS configured + invalid → 401.
    - JWKS not configured → header is ignored, request passes as anonymous.
    """

    def __init__(
        self,
        app: Any,
        *,
        jwks: JWKSCache | None,
        audience: str,
        issuer: str,
    ) -> None:
        super().__init__(app)
        self._jwks = jwks
        self._audience = audience or None
        self._issuer = issuer or None

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.user = None
        header = request.headers.get("authorization")
        if not header:
            return await call_next(request)

        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return _unauthorized("malformed Authorization header")

        if self._jwks is None:
            # JWKS not configured: don't enforce, but don't trust the token either.
            return await call_next(request)

        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            log.info("auth.jwt_header_invalid", error=str(exc))
            return _unauthorized("invalid token header")

        kid = unverified_header.get("kid")
        if not kid:
            return _unauthorized("missing kid in token header")

        key = await self._jwks.get_key(kid)
        if key is None:
            return _unauthorized("unknown signing key")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[unverified_header.get("alg", "RS256")],
                audience=self._audience,
                issuer=self._issuer,
                options={"verify_aud": bool(self._audience), "verify_iss": bool(self._issuer)},
            )
        except JWTError as exc:
            log.info("auth.jwt_invalid", error=str(exc))
            return _unauthorized("invalid token")

        sub = claims.get("sub")
        if not sub:
            return _unauthorized("missing sub claim")

        try:
            user_id = UUID(str(sub))
        except ValueError:
            return _unauthorized("sub is not a UUID")

        request.state.user = CurrentUser(
            id=user_id,
            email=claims.get("email"),
            claims=claims,
        )
        return await call_next(request)


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=401)
