from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

_DUMMY_HASH = bcrypt.hashpw(b"wavygo-timing-only-password", bcrypt.gensalt())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_email(email: str) -> str:
    return email.strip().lower()


normalize_email = normalise_email


def hash_password(password: str) -> str:
    if not 10 <= len(password) or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be 10-72 bytes long.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8") if password_hash else _DUMMY_HASH)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: dict[str, Any]) -> str:
    now = utc_now()
    claims = {"sub": str(user["_id"]), "tenant_id": str(user["tenantId"]), "role": user["role"], "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=settings.access_token_ttl_minutes)}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer, options={"require": ["exp", "iss", "aud", "sub", "tenant_id", "role"]})


def create_refresh_document(user: dict[str, Any], family_id: str | None = None) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(48)
    now = utc_now()
    return token, {"userId": user["_id"], "tenantId": user["tenantId"], "tokenHash": hash_refresh_token(token), "familyId": family_id or str(uuid.uuid4()), "expiresAt": now + timedelta(days=settings.refresh_token_ttl_days), "revokedAt": None, "replacedByTokenId": None, "createdAt": now}
