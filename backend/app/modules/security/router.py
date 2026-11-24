
"""Vendor security centre endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.security import (
    get_current_vendor,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/security", tags=["security"])


def now():
    return datetime.now(timezone.utc)


def db_for(request):
    db = getattr(request.app.state, "database", None)
    if db is None:
        try:
            from app.db.mongodb import create_mongo_client, get_database
            client = create_mongo_client()
            if client is not None:
                db = get_database(client)
                request.app.state.database = db
        except Exception:
            db = None
    if db is None:
        raise HTTPException(503, "Security storage is unavailable.")
    return db


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if isinstance(doc.get("vendor_id"), ObjectId):
        doc["vendor_id"] = str(doc["vendor_id"])
    return doc


def audit(db, vendor, action, request, details=None, severity="info"):
    db["security_audit_logs"].insert_one({
        "vendor_id": vendor["_id"],
        "action": action,
        "severity": severity,
        "details": details or {},
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:500],
        "created_at": now(),
    })


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login_alerts: bool | None = None
    new_device_alerts: bool | None = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class TotpCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^\d{6}$")


@router.get("/overview")
def overview(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    db = db_for(request)
    vid = vendor["_id"]

    return {
        "active_sessions": db.security_sessions.count_documents({
            "vendor_id": vid,
            "revoked_at": None,
            "expires_at": {"$gt": now()},
        }),
        "failed_logins_last_7_days": db.security_login_history.count_documents({
            "vendor_id": vid,
            "success": False,
            "created_at": {"$gte": now() - timedelta(days=7)},
        }),
        "unresolved_alerts": db.security_events.count_documents({
            "vendor_id": vid,
            "resolved": False,
        }),
        "two_factor_enabled": bool(vendor.get("two_factor_enabled", False)),
    }


@router.get("/sessions")
def sessions(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    docs = db_for(request).security_sessions.find({
        "vendor_id": vendor["_id"],
        "revoked_at": None,
        "expires_at": {"$gt": now()},
    }).sort("created_at", -1).limit(100)

    return [serialize(x) for x in docs]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(404, "Session not found.")

    db = db_for(request)
    result = db.security_sessions.update_one(
        {
            "_id": ObjectId(session_id),
            "vendor_id": vendor["_id"],
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now()}},
    )

    if not result.modified_count:
        raise HTTPException(404, "Session not found or already revoked.")

    audit(db, vendor, "session.revoked", request, {"session_id": session_id})
    return {"message": "Session revoked."}


@router.post("/sessions/revoke-all")
def revoke_all(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    db = db_for(request)
    result = db.security_sessions.update_many(
        {"vendor_id": vendor["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now()}},
    )

    audit(
        db,
        vendor,
        "sessions.revoked_all",
        request,
        {"count": result.modified_count},
        "warning",
    )

    return {
        "revoked_count": result.modified_count,
        "message": "All sessions revoked. Sign in again.",
    }


@router.get("/login-history")
def login_history(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
    limit: int = 50,
):
    docs = db_for(request).security_login_history.find(
        {"vendor_id": vendor["_id"]}
    ).sort("created_at", -1).limit(max(1, min(limit, 100)))

    return [serialize(x) for x in docs]


@router.get("/audit-logs")
def get_audit_logs(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
    limit: int = 50,
):
    docs = db_for(request).security_audit_logs.find(
        {"vendor_id": vendor["_id"]}
    ).sort("created_at", -1).limit(max(1, min(limit, 100)))

    return [serialize(x) for x in docs]


@router.get("/alerts")
def alerts(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
    limit: int = 50,
):
    docs = db_for(request).security_events.find(
        {"vendor_id": vendor["_id"]}
    ).sort("created_at", -1).limit(max(1, min(limit, 100)))

    return [serialize(x) for x in docs]


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    if not ObjectId.is_valid(alert_id):
        raise HTTPException(404, "Alert not found.")

    db = db_for(request)
    result = db.security_events.update_one(
        {
            "_id": ObjectId(alert_id),
            "vendor_id": vendor["_id"],
        },
        {"$set": {"resolved": True, "resolved_at": now()}},
    )

    if not result.matched_count:
        raise HTTPException(404, "Alert not found.")

    audit(db, vendor, "alert.resolved", request, {"alert_id": alert_id})
    return {"message": "Alert resolved."}


@router.get("/settings")
def get_settings(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    saved = db_for(request).security_settings.find_one({
        "vendor_id": vendor["_id"],
    }) or {}

    return {
        "login_alerts": saved.get("login_alerts", True),
        "new_device_alerts": saved.get("new_device_alerts", True),
        "two_factor_enabled": bool(vendor.get("two_factor_enabled", False)),
    }


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    changes = payload.model_dump(exclude_none=True)

    if not changes:
        raise HTTPException(400, "Provide at least one setting.")

    db = db_for(request)
    db.security_settings.update_one(
        {"vendor_id": vendor["_id"]},
        {
            "$set": {**changes, "updated_at": now()},
            "$setOnInsert": {"vendor_id": vendor["_id"]},
        },
        upsert=True,
    )

    audit(db, vendor, "security.settings_updated", request, changes)
    return get_settings(request, vendor)


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    if payload.current_password == payload.new_password:
        raise HTTPException(400, "New password must differ from current password.")

    if not verify_password(
        payload.current_password,
        vendor.get("password_hash", ""),
    ):
        raise HTTPException(400, "Current password is incorrect.")

    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    db = db_for(request)
    db.vendors.update_one(
        {"_id": vendor["_id"]},
        {"$set": {"password_hash": new_hash, "password_changed_at": now()}},
    )

    db.security_sessions.update_many(
        {"vendor_id": vendor["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now()}},
    )

    audit(db, vendor, "password.changed", request, severity="warning")

    return {
        "message": "Password changed. All sessions revoked; sign in again."
    }


@router.post("/2fa/setup")
def setup_2fa(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    try:
        import pyotp
    except ImportError as exc:
        raise HTTPException(
            503,
            "Install pyotp to enable authenticator-based 2FA.",
        ) from exc

    if vendor.get("two_factor_enabled"):
        raise HTTPException(409, "2FA is already enabled.")

    secret = pyotp.random_base32()
    db = db_for(request)

    db.vendors.update_one(
        {"_id": vendor["_id"]},
        {"$set": {"two_factor_pending_secret": secret}},
    )

    uri = pyotp.TOTP(secret).provisioning_uri(
        name=vendor.get("email", str(vendor["_id"])),
        issuer_name="WavyGo",
    )

    return {
        "secret": secret,
        "otpauth_uri": uri,
        "message": "Add to an authenticator app, then verify a code to enable 2FA.",
    }


@router.post("/2fa/enable")
def enable_2fa(
    payload: TotpCode,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    try:
        import pyotp
    except ImportError as exc:
        raise HTTPException(503, "Install pyotp to enable 2FA.") from exc

    secret = vendor.get("two_factor_pending_secret")

    if not secret or not pyotp.TOTP(secret).verify(
        payload.code,
        valid_window=1,
    ):
        raise HTTPException(400, "Invalid authenticator code or setup expired.")

    db = db_for(request)
    db.vendors.update_one(
        {"_id": vendor["_id"]},
        {
            "$set": {
                "two_factor_secret": secret,
                "two_factor_enabled": True,
            },
            "$unset": {"two_factor_pending_secret": ""},
        },
    )

    audit(db, vendor, "two_factor.enabled", request, severity="warning")
    return {"message": "Two-factor authentication enabled."}


@router.post("/2fa/disable")
def disable_2fa(
    payload: TotpCode,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    try:
        import pyotp
    except ImportError as exc:
        raise HTTPException(503, "Install pyotp to manage 2FA.") from exc

    secret = vendor.get("two_factor_secret")

    if (
        not vendor.get("two_factor_enabled")
        or not secret
        or not pyotp.TOTP(secret).verify(payload.code, valid_window=1)
    ):
        raise HTTPException(400, "Invalid authenticator code.")

    db = db_for(request)
    db.vendors.update_one(
        {"_id": vendor["_id"]},
        {
            "$set": {"two_factor_enabled": False},
            "$unset": {
                "two_factor_secret": "",
                "two_factor_pending_secret": "",
            },
        },
    )

    db.security_sessions.update_many(
        {"vendor_id": vendor["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now()}},
    )

    audit(db, vendor, "two_factor.disabled", request, severity="warning")
    return {"message": "2FA disabled. All sessions revoked."}
