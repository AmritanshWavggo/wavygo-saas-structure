"""
Route protection test for Customers API.
Ensures every route under /api/v1/customers requires authentication.
"""

from app.main import app
from app.modules.auth.deps import get_current_user


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


def test_customers_routes_are_all_protected():
    customer_routes = [
        route
        for route in _walk_routes(app.routes)
        if getattr(route, "path", "").startswith("/api/v1/customers")
    ]

    assert len(customer_routes) >= 5, f"Expected at least 5 customer routes, found {len(customer_routes)}"

    for route in customer_routes:
        callables = _collect_dependant_callables(getattr(route, "dependant", None))
        assert get_current_user in callables, (
            f"Customer route {route.path} does not have get_current_user in its dependencies."
        )
