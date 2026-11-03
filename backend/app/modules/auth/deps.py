from __future__ import annotations

from typing import Callable

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.mongodb import get_database
from app.modules.auth.models import UserRole
from app.modules.auth.service import decode_access_token

bearer = HTTPBearer(auto_error=False)
TenantContext = dict


def as_object_id(value: str, label: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(401, f"Invalid {label}.")
    return ObjectId(value)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication is required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired access token.")
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database is not available.")
    user_id = as_object_id(claims["sub"], "user")
    tenant_id = as_object_id(claims["tenant_id"], "tenant")
    user = db["users"].find_one({"_id": user_id, "tenantId": tenant_id, "isActive": True})
    if user is None or user.get("role") != claims["role"]:
        raise HTTPException(401, "Account is unavailable.")
    return user


def get_current_tenant(user: dict = Depends(get_current_user)) -> TenantContext:
    return {"tenant_id": user["tenantId"], "user_id": user["_id"], "role": user["role"]}


def require_role(*roles: UserRole) -> Callable:
    allowed = {role.value for role in roles}

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(403, "You do not have permission to perform this action.")
        return user

    return dependency
