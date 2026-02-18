"""
marksync.auth.middleware — FastAPI authentication middleware and dependency helpers.

Usage:
    from marksync.auth.middleware import AuthMiddleware, get_current_user, require_role

    app.add_middleware(AuthMiddleware, skip_paths=["/health", "/api/events"])

    @app.get("/api/protected")
    async def protected(user: TokenPayload = Depends(get_current_user)):
        ...

    @app.post("/api/deploy")
    async def deploy(user: TokenPayload = Depends(require_role("agent"))):
        ...
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from marksync.auth.tokens import TokenPayload, verify_token
from marksync.auth.roles import has_permission

_AUTH_ENABLED = os.environ.get("MARKSYNC_AUTH_ENABLED", "false").lower() in ("1", "true", "yes")

_DEFAULT_SKIP = {"/", "/health", "/api/events", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that validates Bearer tokens on all requests
    except those listed in skip_paths.

    When MARKSYNC_AUTH_ENABLED=false (the default for local dev) all
    requests pass through unauthenticated.
    """

    def __init__(self, app, skip_paths: set[str] | None = None):
        super().__init__(app)
        self.skip_paths: set[str] = skip_paths or _DEFAULT_SKIP

    async def dispatch(self, request: Request, call_next):
        if not _AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in self.skip_paths or any(path.startswith(s) for s in self.skip_paths if s.endswith("/")):
            return await call_next(request)

        token = _extract_token(request)
        if not token:
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        payload = verify_token(token)
        if not payload:
            return JSONResponse(
                {"detail": "Token invalid or expired"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        request.state.user = payload
        return await call_next(request)


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    token = request.query_params.get("token")
    return token or None


async def get_current_user(request: Request) -> TokenPayload | None:
    """
    FastAPI dependency: returns the current TokenPayload if auth is enabled,
    or a guest admin payload when auth is disabled (local dev).
    """
    if not _AUTH_ENABLED:
        return TokenPayload(sub="guest", role="admin")

    if hasattr(request.state, "user"):
        return request.state.user

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return payload


def require_role(action: str) -> Callable:
    """
    FastAPI dependency factory: requires the current user to have permission
    for the given action.

    Usage:
        @app.post("/api/deploy")
        async def deploy(user = Depends(require_role("deploy"))):
            ...
    """
    async def _check(request: Request) -> TokenPayload:
        user = await get_current_user(request)
        if user and not has_permission(user.role, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' cannot perform '{action}'",
            )
        return user
    return _check
