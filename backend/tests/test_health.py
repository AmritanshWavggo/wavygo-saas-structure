from __future__ import annotations

import asyncio
import inspect

import httpx

from app.main import app, health_check

REQUEST_TIMEOUT_SECONDS = 10


async def _request(method: str, path: str) -> httpx.Response:
    # ASGITransport calls the app directly. It does not run startup events,
    # so no MongoDB or Cloudinary configuration is needed.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path)


def request(method: str, path: str) -> httpx.Response:
    # The timeout makes a hang fail the test instead of freezing pytest.
    return asyncio.run(asyncio.wait_for(_request(method, path), timeout=REQUEST_TIMEOUT_SECONDS))


def test_health_function_returns_ok() -> None:
    result = health_check()
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    assert result == {"status": "ok"}


def test_health_route_over_http() -> None:
    response = request("GET", "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_health_route_over_http() -> None:
    response = request("GET", "/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert "status" in body


def test_unknown_route_returns_404() -> None:
    response = request("GET", "/this-route-does-not-exist")
    assert response.status_code == 404


def test_wrong_method_on_health_is_rejected() -> None:
    response = request("POST", "/health")
    assert response.status_code == 405


def test_vehicle_routes_are_registered_with_correct_methods() -> None:
    paths = app.openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/vehicles"])
    assert {"get", "patch", "delete"} <= set(paths["/api/v1/vehicles/{vehicle_id}"])
    assert "patch" in paths["/api/v1/vehicles/{vehicle_id}/show-on-wavygo"]


def test_existing_health_routes_still_registered() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/health"]
    assert "get" in paths["/api/v1/health"]