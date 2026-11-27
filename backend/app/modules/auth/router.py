
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import pyotp
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.modules.auth.security import (
    create_access_token,
    get_vendors_collection,
    hash_password,
    normalize_email,
    verify_password,
)
from app.services.email_service import send_signup_otp_email, send_welcome_email
from app.services.otp_service import (
    check_otp_rate_limit,
    generate_otp,
    store_signup_otp,
    verify_signup_otp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = normalize_email(value)

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")

        return value


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    business_name: str | None = None
    owner_name: str | None = None


class SendOtpRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=254)
    name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = normalize_email(value)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    otp: str = Field(pattern=r"^\d{6}$")
    business_name: str = Field(min_length=2, max_length=120)
    owner_name: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = normalize_email(value)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    vendors: Annotated[
        Collection[dict[str, Any]],
        Depends(get_vendors_collection),
    ],
) -> TokenResponse:
    # Get database if available
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

    attempts = (
        db["security_login_attempts"]
        if db is not None
        else None
    )

    now = datetime.now(timezone.utc)

    attempt_key = credentials.email + ":" + (
        request.client.host
        if request.client
        else "unknown"
    )

    # Check failed login attempts
    recent_failures = (
        attempts.count_documents({
            "key": attempt_key,
            "created_at": {
                "$gte": now - timedelta(minutes=15),
            },
        })
        if attempts is not None
        else 0
    )

    max_failures = 25 if getattr(settings, "app_env", "") == "development" else 5
    if recent_failures >= max_failures:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    # Find vendor
    try:
        vendor = vendors.find_one({
            "email_normalized": credentials.email,
        })
    except PyMongoError as exc:
        logger.exception("Vendor authentication lookup failed.")

        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable.",
        ) from exc

    # Verify credentials
    valid = (
        vendor is not None
        and vendor.get("is_active") is True
        and isinstance(vendor.get("password_hash"), str)
        and verify_password(
            credentials.password,
            vendor["password_hash"],
        )
    )

    # Verify two-factor authentication
    if valid and vendor is not None and vendor.get("two_factor_enabled"):
        try:
            valid = bool(
                credentials.totp_code
                and vendor.get("two_factor_secret")
                and pyotp.TOTP(
                    vendor["two_factor_secret"]
                ).verify(
                    credentials.totp_code,
                    valid_window=1,
                )
            )
        except Exception:
            logger.exception("Two-factor authentication failed.")
            valid = False

    # Handle invalid login
    if not valid or vendor is None:
        if db is not None and attempts is not None:
            attempts.insert_one({
                "key": attempt_key,
                "created_at": now,
            })

            vendor_id_opt = vendor["_id"] if vendor is not None else None
            db["security_login_history"].insert_one({
                "vendor_id": vendor_id_opt,
                "email": credentials.email,
                "success": False,
                "ip_address": (
                    request.client.host
                    if request.client
                    else None
                ),
                "user_agent": request.headers.get(
                    "user-agent", ""
                )[:500],
                "created_at": now,
            })

            prefs = (
                db["security_settings"].find_one({
                    "vendor_id": vendor_id_opt,
                }) or {}
                if vendor_id_opt is not None
                else {}
            )

            if vendor_id_opt is not None and prefs.get("login_alerts", True):
                db["security_events"].insert_one({
                    "vendor_id": vendor_id_opt,
                    "type": "failed_login",
                    "severity": "warning",
                    "message": "A failed sign-in attempt was detected.",
                    "ip_address": (
                        request.client.host
                        if request.client
                        else None
                    ),
                    "resolved": False,
                    "created_at": now,
                })

        raise unauthorized()

    # Clear failed login attempts after successful login
    if attempts is not None:
        attempts.delete_many({
            "key": attempt_key,
        })

    # Compatibility fallback for tests using injected fake collections.
    if db is None:
        session_id = ObjectId()
        token, expires_in = create_access_token(
            str(vendor["_id"]),
            str(session_id),
        )
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            business_name=vendor.get("business_name") or vendor.get("businessName"),
            owner_name=vendor.get("owner_name") or vendor.get("ownerName") or vendor.get("owner"),
        )

    # Check previous session and device
    previous_session = (
        db["security_sessions"].find_one({"vendor_id": vendor["_id"]})
        if db is not None
        else None
    )

    prefs = (
        db["security_settings"].find_one({"vendor_id": vendor["_id"]}) or {}
        if db is not None
        else {}
    )

    current_ip = (
        request.client.host
        if request.client
        else None
    )

    current_agent = request.headers.get(
        "user-agent", ""
    )[:500]

    # Detect new device or network
    if db is not None and previous_session and prefs.get("new_device_alerts", True):
        if (
            previous_session.get("ip_address") != current_ip
            or previous_session.get("user_agent") != current_agent
        ):
            db["security_events"].insert_one({
                "vendor_id": vendor["_id"],
                "type": "new_device",
                "severity": "warning",
                "message": "A sign-in from a new device or network was detected.",
                "ip_address": current_ip,
                "user_agent": current_agent,
                "resolved": False,
                "created_at": now,
            })

    # Create new session
    session_id = ObjectId()
    expires_at = now + timedelta(
        minutes=settings.jwt_access_token_minutes,
    )

    if db is not None:
        db["security_sessions"].insert_one({
            "_id": session_id,
            "vendor_id": vendor["_id"],
            "ip_address": current_ip,
            "user_agent": current_agent,
            "created_at": now,
            "last_seen_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
        })

        # Save successful login history
        db["security_login_history"].insert_one({
            "vendor_id": vendor["_id"],
            "email": credentials.email,
            "success": True,
            "ip_address": current_ip,
            "user_agent": current_agent,
            "created_at": now,
        })

    # Clear failed login attempts after successful login
    if attempts is not None:
        attempts.delete_many({
            "key": attempt_key,
        })

    # Generate access token
    token, expires_in = create_access_token(
        str(vendor["_id"]),
        str(session_id),
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        business_name=vendor.get("business_name") or vendor.get("businessName"),
        owner_name=vendor.get("owner_name") or vendor.get("ownerName") or vendor.get("owner"),
    )

@router.post("/signup/send-otp")
def send_signup_otp(
    payload: SendOtpRequest,
    vendors: Annotated[
        Collection[dict[str, Any]],
        Depends(get_vendors_collection),
    ],
) -> dict[str, str]:
    """Generate and email a 6-digit verification code to the vendor for signup."""
    # Check if active account already exists
    try:
        existing = vendors.find_one({"email_normalized": payload.email})
        if existing and existing.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please sign in.",
            )
    except PyMongoError as exc:
        logger.exception("Vendor lookup failed during OTP request.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    # Rate limiting: 30-second cooldown
    can_send, wait_secs = check_otp_rate_limit(payload.email)
    if not can_send:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait_secs} seconds before requesting a new code.",
        )

    # Generate 6-digit OTP
    otp = generate_otp(6)
    store_signup_otp(payload.email, otp, ttl_seconds=600)

    # Send email via Brevo
    email_sent = send_signup_otp_email(payload.email, otp, payload.name)
    if not email_sent:
        logger.warning("Brevo email send failed or skipped for %s. OTP stored in cache.", payload.email)

    return {
        "message": "Verification code has been sent to your email.",
        "email": payload.email,
    }


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    vendors: Annotated[
        Collection[dict[str, Any]],
        Depends(get_vendors_collection),
    ],
) -> TokenResponse:
    """Verify OTP and register a new vendor partner account."""
    # 1. Verify OTP from Upstash Redis or fallback store
    if not verify_signup_otp(payload.email, payload.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    # 2. Check if vendor exists
    try:
        existing = vendors.find_one({"email_normalized": payload.email})
        if existing and existing.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please sign in.",
            )
    except PyMongoError as exc:
        logger.exception("Vendor lookup failed during signup.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

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

    now = datetime.now(timezone.utc)
    vendor_id = ObjectId()

    # 3. Hash password
    try:
        hashed_password = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 4. Insert new vendor record
    vendor_doc = {
        "_id": vendor_id,
        "email": payload.email,
        "email_normalized": payload.email,
        "password_hash": hashed_password,
        "business_name": payload.business_name.strip(),
        "owner_name": (payload.owner_name or payload.business_name).strip(),
        "phone": (payload.phone or "").strip(),
        "city": (payload.city or "Bengaluru").strip(),
        "state": (payload.state or "Karnataka").strip(),
        "address": "",
        "is_active": True,
        "email_verified": True,
        "plan": "Growth",
        "rental_rules": {
            "minimumRentalHours": 24,
            "advanceBookingDays": 90,
            "defaultSecurityDeposit": 2000.0,
            "cancellationHours": 24,
            "currency": "INR",
        },
        "created_at": now,
        "updated_at": now,
    }

    try:
        vendors.insert_one(vendor_doc)
    except PyMongoError as exc:
        logger.exception("Failed to insert new vendor.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not complete registration. Please try again.",
        ) from exc

    # 5. Create initial session & token
    session_id = ObjectId()
    current_ip = request.client.host if request.client else None
    current_agent = request.headers.get("user-agent", "")[:500]

    if db is not None:
        expires_at = now + timedelta(minutes=settings.jwt_access_token_minutes)
        db["security_sessions"].insert_one({
            "_id": session_id,
            "vendor_id": vendor_id,
            "ip_address": current_ip,
            "user_agent": current_agent,
            "created_at": now,
            "last_seen_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
        })
        db["security_login_history"].insert_one({
            "vendor_id": vendor_id,
            "email": payload.email,
            "success": True,
            "ip_address": current_ip,
            "user_agent": current_agent,
            "created_at": now,
        })

    token, expires_in = create_access_token(str(vendor_id), str(session_id))

    # 6. Send welcome email asynchronously/safely
    try:
        send_welcome_email(payload.email, payload.business_name)
    except Exception as exc:
        logger.warning("Welcome email failed: %s", exc)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        business_name=payload.business_name,
        owner_name=payload.owner_name or payload.business_name,
    )
