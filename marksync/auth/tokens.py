"""
marksync.auth.tokens — JWT token generation and validation.

Uses PyJWT when available; falls back to a simple HMAC-based token when not.

Environment variables:
    MARKSYNC_SECRET_KEY   — signing key (required in production)
    MARKSYNC_TOKEN_TTL    — token lifetime in seconds (default: 86400 = 24h)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field


_SECRET = os.environ.get("MARKSYNC_SECRET_KEY", "marksync-dev-secret-change-me")
_TTL = int(os.environ.get("MARKSYNC_TOKEN_TTL", "86400"))


@dataclass
class TokenPayload:
    """Decoded JWT / token payload."""
    sub: str            # subject (user or agent id)
    role: str           # Role value string
    iat: float = field(default_factory=time.time)
    exp: float = 0.0

    def __post_init__(self):
        if not self.exp:
            self.exp = self.iat + _TTL

    def is_expired(self) -> bool:
        return time.time() > self.exp

    def to_dict(self) -> dict:
        return {"sub": self.sub, "role": self.role, "iat": self.iat, "exp": self.exp}


# ── JWT backend (preferred) ────────────────────────────────────────────────

def _try_jwt_encode(payload: dict) -> str | None:
    try:
        import jwt
        return jwt.encode(payload, _SECRET, algorithm="HS256")
    except ImportError:
        return None


def _try_jwt_decode(token: str) -> dict | None:
    try:
        import jwt
        return jwt.decode(token, _SECRET, algorithms=["HS256"])
    except ImportError:
        return None
    except Exception:
        return None


# ── Fallback HMAC backend ──────────────────────────────────────────────────

def _hmac_encode(payload: dict) -> str:
    import base64
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}.{sig}"


def _hmac_decode(token: str) -> dict | None:
    import base64
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        padding = 4 - len(body) % 4
        body += "=" * padding
        return json.loads(base64.urlsafe_b64decode(body).decode())
    except Exception:
        return None


# ── Public API ─────────────────────────────────────────────────────────────

def create_token(subject: str, role: str = "viewer", ttl: int | None = None) -> str:
    """
    Create a signed token for the given subject and role.

    Args:
        subject: User/agent identifier.
        role:    Role string ("admin", "agent", "viewer").
        ttl:     Override token lifetime in seconds.

    Returns:
        Token string (JWT if PyJWT installed, else HMAC token).
    """
    now = time.time()
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + (ttl if ttl is not None else _TTL),
    }
    result = _try_jwt_encode(payload)
    if result is not None:
        return result
    return _hmac_encode(payload)


def verify_token(token: str) -> TokenPayload | None:
    """
    Verify and decode a token.

    Returns:
        TokenPayload if valid and not expired, None otherwise.
    """
    if not token:
        return None

    payload = _try_jwt_decode(token)
    if payload is None:
        payload = _hmac_decode(token)
    if payload is None:
        return None

    tp = TokenPayload(
        sub=payload.get("sub", ""),
        role=payload.get("role", "viewer"),
        iat=payload.get("iat", 0.0),
        exp=payload.get("exp", 0.0),
    )
    if tp.is_expired():
        return None
    return tp
