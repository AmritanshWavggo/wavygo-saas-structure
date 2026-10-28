"""
Auth dependency stubs.

``get_current_tenant`` is the single auth dependency used by every vehicle
route (and future routes).  It currently returns a minimal tenant context dict
so that routes can be developed and tested without a real auth system.

REPLACE the body of this function with JWT / API-key validation when the auth
module is fully implemented.  The return shape must remain a dict with at least:
    {
        "tenant_id": str,   # used to scope DB queries per-tenant
        "role":      str,   # e.g. "owner", "staff"
    }

No external libraries are needed by this stub.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tenant context type alias
# ---------------------------------------------------------------------------
TenantContext = dict  # plain dict — tighten to a TypedDict/Pydantic model later


def get_current_tenant() -> TenantContext:
    """
    FastAPI dependency — returns the current tenant's context.

    Current behaviour (stub): always succeeds and returns a development
    tenant context.  Swap this out for real JWT parsing / DB lookup when
    the auth module is implemented.

    Usage in a route::

        from typing import Annotated
        from fastapi import Depends
        from app.modules.auth.deps import get_current_tenant, TenantContext

        @router.get("/vehicles")
        def list_vehicles(tenant: Annotated[TenantContext, Depends(get_current_tenant)]):
            ...
    """
    # TODO: parse Bearer token / session cookie; raise HTTP 401 if invalid.
    return {"tenant_id": "dev_tenant", "role": "owner"}
