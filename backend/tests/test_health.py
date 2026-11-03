from app.core.responses import error_payload
from app.main import app, health_check


def test_health_functions_return_envelopes() -> None:
    assert health_check() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_error_envelope_shape() -> None:
    assert error_payload("NOT_FOUND", "Not found.") == {
        "success": False,
        "data": None,
        "error": {"code": "NOT_FOUND", "message": "Not found."},
    }


def test_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert {"get", "post"} <= set(paths["/api/v1/vehicles"])
    assert {"get", "patch", "delete"} <= set(paths["/api/v1/vehicles/{vehicle_id}"])
    assert {"post", "get"} <= set(paths["/api/v1/auth/login"]) | set(paths["/api/v1/auth/me"])
