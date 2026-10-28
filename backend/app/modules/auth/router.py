import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.modules.auth.security import (
    create_access_token,
    get_vendors_collection,
    normalize_email,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = normalize_email(value)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    vendors: Annotated[Collection[dict], Depends(get_vendors_collection)],
) -> TokenResponse:
    try:
        vendor = vendors.find_one({"email_normalized": credentials.email})
    except PyMongoError as exc:
        logger.exception("Vendor authentication lookup failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    if (
        vendor is None
        or vendor.get("is_active") is not True
        or not isinstance(vendor.get("password_hash"), str)
        or not verify_password(credentials.password, vendor["password_hash"])
    ):
        raise unauthorized()

    token, expires_in = create_access_token(str(vendor["_id"]))
    return TokenResponse(access_token=token, expires_in=expires_in)
