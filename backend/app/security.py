"""Security helpers: anonymous session hashing, password hashing, admin tokens.

No third-party auth service is required. Secrets come from the environment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException, status

from .config import settings

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_session_id(session_id: str | None) -> str | None:
    """Return a stable, non-reversible identifier for an anonymous session."""
    if not session_id:
        return None
    cleaned = session_id.strip()
    if not 8 <= len(cleaned) <= 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-Id must be between 8 and 128 characters.",
        )
    return hmac.new(
        settings.secret_key.encode("utf-8"), cleaned.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def require_session_id(x_session_id: str | None = Header(default=None)) -> str:
    """Dependency for routes that need an anonymous session identifier."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Session-Id header. The web app creates one automatically.",
        )
    hashed = hash_session_id(x_session_id)
    assert hashed is not None
    return hashed


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return "scrypt${}${}${}${}".format(
        base64.b64encode(salt).decode(), _SCRYPT_N, _SCRYPT_R,
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, n, r, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=_SCRYPT_P, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_admin_token(username: str, ttl_minutes: int | None = None) -> str:
    ttl = ttl_minutes or settings.admin_token_ttl_minutes
    payload = {"sub": username, "exp": int(time.time()) + ttl * 60}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def decode_admin_token(token: str) -> str:
    try:
        body, signature = token.split(".")
        expected = hmac.new(
            settings.secret_key.encode(), body.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("bad signature")
        payload = json.loads(_b64decode(body))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return str(payload["sub"])
    except Exception as exc:  # noqa: BLE001 - normalise all failures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired or invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_admin(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_admin_token(authorization.split(" ", 1)[1].strip())
