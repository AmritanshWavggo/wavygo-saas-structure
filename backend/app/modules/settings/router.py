"""Vendor settings endpoints."""

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
from app.modules.security.router import (
    now,
    db_for,
    serialize,
    audit,
    SettingsUpdate,
    PasswordChange,
    TotpCode,
    overview,
    sessions,
    revoke_session,
    revoke_all,
    login_history,
    get_audit_logs,
    alerts,
    resolve_alert,
    get_settings,
    update_settings,
    change_password,
    setup_2fa,
    enable_2fa,
    disable_2fa,
)

router = APIRouter(prefix="/settings", tags=["settings"])

router.add_api_route("/overview", overview, methods=["GET"])
router.add_api_route("/sessions", sessions, methods=["GET"])
router.add_api_route("/sessions/{session_id}", revoke_session, methods=["DELETE"])
router.add_api_route("/sessions/revoke-all", revoke_all, methods=["POST"])
router.add_api_route("/login-history", login_history, methods=["GET"])
router.add_api_route("/audit-logs", get_audit_logs, methods=["GET"])
router.add_api_route("/alerts", alerts, methods=["GET"])
router.add_api_route("/alerts/{alert_id}/resolve", resolve_alert, methods=["POST"])
router.add_api_route("", get_settings, methods=["GET"])
router.add_api_route("", update_settings, methods=["PUT"])
router.add_api_route("/security", get_settings, methods=["GET"])
router.add_api_route("/security", update_settings, methods=["PUT"])
router.add_api_route("/change-password", change_password, methods=["POST"])
router.add_api_route("/2fa/setup", setup_2fa, methods=["POST"])
router.add_api_route("/2fa/enable", enable_2fa, methods=["POST"])
router.add_api_route("/2fa/disable", disable_2fa, methods=["POST"])

