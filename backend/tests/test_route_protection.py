from __future__ import annotations

import pytest
from app.main import app
from app.modules.auth.deps import get_current_user

ALLOWED_UNAUTHENTICATED_PATHS = {
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


def test_every_vehicle_route_has_auth_dependency():
    vehicle_routes = [
        route
        for route in _walk_routes(app.routes)
        if getattr(route, "path", "").startswith("/api/v1/vehicles")
    ]
    assert len(vehicle_routes) >= 6, "Expected at least 6 vehicle routes to be registered."

    for route in vehicle_routes:
        callables = _collect_dependant_callables(getattr(route, "dependant", None))
        assert get_current_user in callables, (
            f"Route {route.path} does not have get_current_user (or require_role) in its dependencies."
        )


def test_only_allowed_routes_are_unauthenticated():
    open_routes = []
    for route in _walk_routes(app.routes):
        path = getattr(route, "path", None)
        if not path or path in DOCS_PATHS:
            continue
        callables = _collect_dependant_callables(getattr(route, "dependant", None))
        has_auth = get_current_user in callables
        if not has_auth:
            open_routes.append(path)

    open_routes_set = set(open_routes)
    unexpected_open = open_routes_set - ALLOWED_UNAUTHENTICATED_PATHS
    assert not unexpected_open, f"Found unauthenticated routes that are not allowed: {unexpected_open}"
    assert open_routes_set == ALLOWED_UNAUTHENTICATED_PATHS, (
        f"Expected open routes to be exactly {ALLOWED_UNAUTHENTICATED_PATHS}, got {open_routes_set}"
    )

