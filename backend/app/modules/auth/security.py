import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "wavygo-api"
JWT_AUDIENCE = "wavygo-vendor"
PASSWORD_HASHER = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Passwords must be between 12 and 128 characters.")
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password, password_hash)
    except UnknownHashError:
        return False


def get_jwt_secret() -> str:
    configured_secret = settings.jwt_secret_key
    if configured_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    secret = configured_secret.get_secret_value()
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    return secret


def create_access_token(vendor_id: str) -> tuple[str, int]:
    expires_in = settings.jwt_access_token_minutes * 60
    now = datetime.now(timezone.utc)
    claims = {
        "sub": vendor_id,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "type": "access",
    }
    return jwt.encode(claims, get_jwt_secret(), algorithm=JWT_ALGORITHM), expires_in


def get_vendors_collection(request: Request) -> Collection[dict[str, Any]]:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication storage is unavailable.",
        )

    collection: Collection[dict[str, Any]] = database["vendors"]
    if not getattr(request.app.state, "vendor_indexes_ready", False):
        try:
            collection.create_index(
                [("email_normalized", ASCENDING)],
                unique=True,
                name="vendor_email_normalized_unique",
            )
        except PyMongoError as exc:
            logger.exception("Could not initialize vendor indexes.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication storage is unavailable.",
            ) from exc
        request.app.state.vendor_indexes_ready = True
    return collection


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_vendor(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    vendors: Annotated[
        Collection[dict[str, Any]], Depends(get_vendors_collection)
    ],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()

    try:
        claims = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
    except InvalidTokenError:
        raise unauthorized() from None

    subject = claims.get("sub")
    if (
        claims.get("type") != "access"
        or not isinstance(subject, str)
        or not ObjectId.is_valid(subject)
    ):
        raise unauthorized()

    try:
        vendor = vendors.find_one({"_id": ObjectId(subject), "is_active": True})
    except PyMongoError as exc:
        logger.exception("Vendor authorization lookup failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc
    if vendor is None:
        raise unauthorized()
    return vendor
