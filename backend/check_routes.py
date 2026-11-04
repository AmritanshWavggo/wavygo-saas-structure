#!/usr/bin/env python3
"""
Route inspector script: lists every registered route in the FastAPI application
as AUTH or OPEN based on the presence of get_current_user / get_current_tenant
in its dependency tree.
"""

from __future__ import annotations

import sys

from app.main import app
from app.modules.auth.deps import get_current_tenant, get_current_user

ALLOWED_OPEN_PATHS = {
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}

DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def _collect_dependant_callables(dependant) -> set:
    callables = set()
    if not dependant:
        return callables
    if getattr(dependant, "call", None):
        callables.add(dependant.call)
    for sub in getattr(dependant, "dependencies", []):
        callables |= _collect_dependant_callables(sub)
    return callables


def _walk_routes(routes):
    for route in routes:
        if hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()
        elif hasattr(route, "routes"):
            yield from _walk_routes(route.routes)
        else:
            yield route


def main() -> int:
    routes = list(_walk_routes(app.routes))
    # Filter out routes without a path (e.g. root router wrappers) and docs paths
    items = [
        r for r in routes
        if getattr(r, "path", None) and getattr(r, "path", "") not in DOCS_PATHS
    ]

    # Deduplicate by (methods, path)
    seen = {}
    for r in items:
        path = getattr(r, "path", "")
        methods = ",".join(sorted(getattr(r, "methods", [])))
        if not methods:
            continue
        key = (path, methods)
        if key not in seen:
            seen[key] = r

    unique_routes = list(seen.values())
    unique_routes.sort(key=lambda r: (getattr(r, "path", ""), sorted(getattr(r, "methods", []))))

    print(f"{'STATUS':<8} {'METHODS':<22} {'PATH'}")
    print("-" * 75)

    unexpected_open = []

    for route in unique_routes:
        path = getattr(route, "path", "")
        methods = ",".join(sorted(getattr(route, "methods", [])))
        callables = _collect_dependant_callables(getattr(route, "dependant", None))

        is_auth = (
            get_current_user in callables
            or get_current_tenant in callables
            or any(
                getattr(c, "__name__", "") == "dependency" and "require_role" in getattr(c, "__qualname__", "")
                for c in callables
            )
        )

        if is_auth:
            status = "AUTH"
        else:
            status = "OPEN"
            if path not in ALLOWED_OPEN_PATHS:
                unexpected_open.append((methods, path))

        print(f"{status:<8} {methods:<22} {path}")

    print("-" * 75)

    if unexpected_open:
        print(f"\nERROR: Unexpected OPEN routes detected ({len(unexpected_open)}):")
        for m, p in unexpected_open:
            print(f"  - {m} {p}")
        return 1

    print("\nSUCCESS: All non-auth routes are strictly within ALLOWED_OPEN_PATHS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
