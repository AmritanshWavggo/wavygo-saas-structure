from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import mongodb
from app.main import app
from app.modules.auth import router as auth_router


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_mock_db(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-must-be-at-least-32-bytes-long!")
    monkeypatch.setattr(settings, "mongodb_uri", "mongodb://mock")

    # Reset the in-memory limiter
    with auth_router._attempt_lock:
        auth_router._attempts.clear()

    client = mongomock.MongoClient()
    db = client[settings.mongodb_database]
    monkeypatch.setattr(mongodb, "get_database", lambda c=None: db)
    monkeypatch.setattr(mongodb, "create_mongo_client", lambda: client)
    monkeypatch.setattr(auth_router, "get_database", lambda c=None: db)

    yield

    with auth_router._attempt_lock:
        auth_router._attempts.clear()


def test_email_rate_limit_blocks_on_6th_attempt():
    target_email = "target@example.com"
    other_email = "other@example.com"

    # 5 failed logins for one email across different IPs
    for i in range(1, 6):
        with TestClient(app, client=(f"10.0.0.{i}", 50000)) as client:
            res = client.post(
                "/api/v1/auth/login",
                json={"email": target_email, "password": "WrongPassword123"},
            )
            assert res.status_code == 401

    # 6th failed login for the same email returns 429 with envelope
    with TestClient(app, client=("10.0.0.6", 50000)) as client:
        res_6 = client.post(
            "/api/v1/auth/login",
            json={"email": target_email, "password": "WrongPassword123"},
        )
        assert res_6.status_code == 429
        body = res_6.json()
        assert body["success"] is False
        assert body["data"] is None
        assert "error" in body
        assert body["error"]["code"] in ("TOO_MANY_REQUESTS", "REQUEST_ERROR")
        assert "Too many login attempts" in body["error"]["message"]

    # A different email from one of the earlier IPs (e.g. 10.0.0.1) is NOT blocked
    # because that IP only had 1 attempt.
    with TestClient(app, client=("10.0.0.1", 50000)) as client:
        res_other = client.post(
            "/api/v1/auth/login",
            json={"email": other_email, "password": "WrongPassword123"},
        )
        assert res_other.status_code == 401


def test_per_ip_rate_limit_blocks_on_6th_attempt_across_different_emails():
    test_ip = "192.168.1.50"

    # 5 failed logins from the same IP with 5 different emails
    for i in range(1, 6):
        with TestClient(app, client=(test_ip, 50000)) as client:
            res = client.post(
                "/api/v1/auth/login",
                json={"email": f"different{i}@example.com", "password": "WrongPassword123"},
            )
            assert res.status_code == 401

    # 6th attempt from the same IP with a new email hits the per-IP limit -> 429
    with TestClient(app, client=(test_ip, 50000)) as client:
        res_6 = client.post(
            "/api/v1/auth/login",
            json={"email": "brandnew@example.com", "password": "WrongPassword123"},
        )
        assert res_6.status_code == 429
        body = res_6.json()
        assert body["success"] is False
        assert body["data"] is None
        assert "error" in body
        assert body["error"]["code"] in ("TOO_MANY_REQUESTS", "REQUEST_ERROR")
        assert "Too many login attempts" in body["error"]["message"]

    # The same brandnew@example.com from a DIFFERENT IP is NOT blocked
    with TestClient(app, client=("192.168.1.99", 50000)) as client:
        res_diff_ip = client.post(
            "/api/v1/auth/login",
            json={"email": "brandnew@example.com", "password": "WrongPassword123"},
        )
        assert res_diff_ip.status_code == 401

