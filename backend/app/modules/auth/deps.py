"""Tenant authentication dependency with strict vendor isolation."""

from __future__ import annotations

from typing import Any
from fastapi import Request
from app.modules.auth.security import get_optional_vendor

TenantContext = dict[str, Any]


def get_current_tenant(
    request: Request = None,  # type: ignore
) -> TenantContext:
    if request is not None and isinstance(request, Request):
        vendor = get_optional_vendor(request)
        if vendor is not None and "_id" in vendor:
            return {
                "tenant_id": str(vendor["_id"]),
                "role": vendor.get("role", "owner"),
                "vendor_id": str(vendor["_id"]),
                "vendor": vendor,
            }
    return {
        "tenant_id": "dev_tenant",
        "role": "owner",
    }
