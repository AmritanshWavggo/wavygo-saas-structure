import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
try:
    from pwdlib import PasswordHash
    from pwdlib.exceptions import UnknownHashError
    PASSWORD_HASHER = PasswordHash.recommended()
except ImportError:
    PASSWORD_HASHER = None
    UnknownHashError = Exception
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "wavygo-api"
JWT_AUDIENCE = "wavygo-vendor"

bearer_scheme = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 128:
        raise ValueError(
            "Passwords must be between 12 and 128 characters."
        )

    if PASSWORD_HASHER is not None:
        return PASSWORD_HASHER.hash(password)

    import hashlib, secrets
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if PASSWORD_HASHER is not None:
            return PASSWORD_HASHER.verify(password, password_hash)
        if password_hash.startswith("pbkdf2_sha256$"):
            import hashlib, hmac
            parts = password_hash.split("$")
            if len(parts) == 4:
                _, iterations, salt, key_hex = parts
                test_key = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
                )
                return hmac.compare_digest(test_key.hex(), key_hex)
        return False
    except Exception:
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


def create_access_token(
    vendor_id: str,
    session_id: str | None = None,
) -> tuple[str, int]:
    expires_in = settings.jwt_access_token_minutes * 60
    now = datetime.now(timezone.utc)
    if session_id is None:
        session_id = str(ObjectId())

    claims = {
        "sub": vendor_id,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "type": "access",
        "jti": session_id,
    }

    token = jwt.encode(
        claims,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )


def get_optional_vendor(
    request: Request,
) -> dict[str, Any] | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token)
        subject = claims.get("sub")
        if not subject:
            return None
        database = getattr(request.app.state, "database", None)
        if database is None:
            from app.db.mongodb import create_mongo_client, get_database
            client = create_mongo_client()
            if client is not None:
                database = get_database(client)
        if database is not None:
            query = {"_id": ObjectId(subject)} if ObjectId.is_valid(subject) else {"_id": subject}
            vendor = database["vendors"].find_one(query)
            if vendor:
                return vendor
        return {"_id": subject, "id": str(subject), "is_active": True}
    except Exception:
        return None


def get_vendors_collection(
    request: Request,
) -> Collection[dict[str, Any]]:
    database = getattr(
        request.app.state,
        "database",
        None,
    )

    if database is None:
        try:
            from app.db.mongodb import create_mongo_client, get_database
            client = create_mongo_client()
            if client is not None:
                database = get_database(client)
                request.app.state.database = database
        except Exception:
            database = None

    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication storage is unavailable.",
        )

    collection = database["vendors"]

    if not getattr(
        request.app.state,
        "vendor_indexes_ready",
        False,
    ):
        try:
            collection.create_index(
                [("email_normalized", ASCENDING)],
                unique=True,
                name="vendor_email_normalized_unique",
            )
        except PyMongoError as exc:
            logger.exception(
                "Could not initialize vendor indexes."
            )
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
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    vendors: Annotated[
        Collection[dict[str, Any]],
        Depends(get_vendors_collection),
    ],
) -> dict[str, Any]:
    # 1. Check bearer token
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
    ):
        raise unauthorized()

    # 2. Decode and validate JWT
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

    # 3. Validate vendor ID
    subject = claims.get("sub")
    if (
        claims.get("type") != "access"
        or not isinstance(subject, str)
        or not ObjectId.is_valid(subject)
    ):
        raise unauthorized()

    # 4. Find active vendor
    try:
        vendor = vendors.find_one({
            "_id": ObjectId(subject),
            "is_active": True,
        })
    except PyMongoError as exc:
        logger.exception(
            "Vendor authorization lookup failed."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    if vendor is None:
        raise unauthorized()

    # 5. Validate session when MongoDB is configured and token contains jti
    session_id = claims.get("jti")
    database = getattr(
        request.app.state,
        "database",
        None,
    )

    if database is not None and isinstance(session_id, str) and ObjectId.is_valid(session_id):
        try:
            session = database["security_sessions"].find_one({
                "_id": ObjectId(session_id),
                "vendor_id": vendor["_id"],
                "revoked_at": None,
                "expires_at": {
                    "$gt": datetime.now(timezone.utc),
                },
            })
        except PyMongoError as exc:
            logger.exception(
                "Vendor session lookup failed."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is unavailable.",
            ) from exc

        if session is None:
            raise unauthorized()

    return vendor
