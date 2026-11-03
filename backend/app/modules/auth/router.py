from __future__ import annotations

from datetime import datetime
from threading import Lock

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response

from app.core.config import settings
from app.core.responses import success
from app.db.mongodb import get_database
from app.modules.auth.deps import get_current_user
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import create_access_token, create_refresh_document, hash_refresh_token, normalise_email, utc_now, verify_password

router = APIRouter()
_attempts: dict[str, list[datetime]] = {}
_attempt_lock = Lock()


def _user_response(user: dict) -> dict:
    return {"id": str(user["_id"]), "tenantId": str(user["tenantId"]), "email": user["email"], "role": user["role"]}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request, email: str) -> None:
    now = utc_now()
    with _attempt_lock:
        for key in (f"ip:{_client_ip(request)}", f"email:{email}"):
            hits = [hit for hit in _attempts.get(key, []) if (now - hit).total_seconds() < 900]
            if len(hits) >= 5:
                raise HTTPException(429, "Too many login attempts. Try again later.")
            _attempts[key] = hits


def _record_failure(request: Request, email: str) -> None:
    with _attempt_lock:
        for key in (f"ip:{_client_ip(request)}", f"email:{email}"):
            _attempts.setdefault(key, []).append(utc_now())


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in settings.frontend_origins:
        raise HTTPException(403, "Invalid request origin.")


def _rotate_refresh_token(db, token_doc: dict, user: dict, now):
    """Atomically consume a refresh token and issue a replacement.

    Uses a single ``find_one_and_update`` with the filter
    ``{tokenHash, revokedAt: null, expiresAt: {$gt: now}}`` so the
    operation is safe on standalone MongoDB (no transaction required).

    If the atomic update matches nothing the token was already consumed
    — treat this as token-reuse and revoke the entire family.
    """
    refresh_token, next_doc = create_refresh_document(user, token_doc["familyId"])
    next_id = db["refresh_tokens"].insert_one(next_doc).inserted_id

    revoked = db["refresh_tokens"].find_one_and_update(
        {
            "tokenHash": token_doc["tokenHash"],
            "revokedAt": None,
            "expiresAt": {"$gt": now},
        },
        {"$set": {"revokedAt": now, "replacedByTokenId": next_id}},
    )
    if revoked is None:
        # Token was already consumed → reuse detected.  Revoke the
        # entire family *including* the freshly-inserted successor.
        db["refresh_tokens"].update_many(
            {"familyId": token_doc["familyId"]},
            {"$set": {"revokedAt": now}},
        )
        raise HTTPException(401, "Refresh token is no longer valid.")

    return refresh_token


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie("wavygo_refresh", token, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/api/v1/auth", max_age=settings.refresh_token_ttl_days * 86400)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    email = normalise_email(str(payload.email))
    _rate_limit(request, email)
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database is not available.")
    user = db["users"].find_one({"email": email})
    password_is_valid = verify_password(payload.password, user.get("passwordHash") if user else None)
    if user is None or not user.get("isActive", False) or not password_is_valid:
        _record_failure(request, email)
        raise HTTPException(401, "Invalid email or password.")
    refresh, document = create_refresh_document(user)
    db["refresh_tokens"].insert_one(document)
    _set_cookie(response, refresh)
    return success({"accessToken": create_access_token(user), "user": _user_response(user)})


@router.post("/refresh")
def refresh(request: Request, response: Response, wavygo_refresh: str | None = Cookie(default=None)):
    _same_origin(request)
    if not wavygo_refresh:
        raise HTTPException(401, "Refresh token is required.")
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database is not available.")
    token_doc = db["refresh_tokens"].find_one({"tokenHash": hash_refresh_token(wavygo_refresh)})
    now = utc_now()
    if token_doc is None:
        raise HTTPException(401, "Invalid refresh token.")
    if token_doc.get("revokedAt") is not None or token_doc["expiresAt"] <= now:
        db["refresh_tokens"].update_many({"familyId": token_doc["familyId"]}, {"$set": {"revokedAt": now}})
        raise HTTPException(401, "Refresh token is no longer valid.")
    user = db["users"].find_one({"_id": token_doc["userId"], "tenantId": token_doc["tenantId"], "isActive": True})
    if user is None:
        db["refresh_tokens"].update_many({"familyId": token_doc["familyId"]}, {"$set": {"revokedAt": now}})
        raise HTTPException(401, "Account is unavailable.")
    refresh_token = _rotate_refresh_token(db, token_doc, user, now)
    _set_cookie(response, refresh_token)
    return success({"accessToken": create_access_token(user), "user": _user_response(user)})


@router.post("/logout")
def logout(request: Request, response: Response, wavygo_refresh: str | None = Cookie(default=None)):
    _same_origin(request)
    db = get_database()
    if db is not None and wavygo_refresh:
        db["refresh_tokens"].update_one({"tokenHash": hash_refresh_token(wavygo_refresh)}, {"$set": {"revokedAt": utc_now()}})
    response.delete_cookie("wavygo_refresh", path="/api/v1/auth")
    return success({"loggedOut": True})


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return success(_user_response(user))
