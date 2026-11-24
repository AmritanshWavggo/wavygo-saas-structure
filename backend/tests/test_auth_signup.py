from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.modules.auth.security import get_vendors_collection, hash_password
from app.services import otp_service


class FakeCollection:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.docs: list[dict[str, Any]] = []

    def insert_one(self, doc: dict[str, Any]) -> Any:
        doc_copy = deepcopy(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = ObjectId()
        self.docs.append(doc_copy)
        return type("InsertResult", (), {"inserted_id": doc_copy["_id"]})()

    def find_one(self, filt: dict[str, Any] | None = None) -> dict[str, Any] | None:
        matches = self.find(filt)
        return deepcopy(matches.docs[0]) if matches.docs else None

    def find(self, filt: dict[str, Any] | None = None) -> Any:
        class FakeCursor:
            def __init__(self, docs):
                self.docs = list(docs)
            def __iter__(self):
                return iter(self.docs)
            def __len__(self):
                return len(self.docs)
        if not filt:
            return FakeCursor(self.docs)
        result = []
        for d in self.docs:
            matched = True
            for k, v in filt.items():
                if d.get(k) != v:
                    matched = False
                    break
            if matched:
                result.append(d)
        return FakeCursor(result)

    def count_documents(self, filt: dict[str, Any] | None = None) -> int:
        return len(self.find(filt))

    def delete_many(self, filt: dict[str, Any] | None = None) -> None:
        pass


class FakeDatabase:
    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self.collections = collections

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]


@pytest.fixture
def auth_env():
    vendors_col = FakeCollection("vendors")
    fake_db = FakeDatabase({
        "vendors": vendors_col,
        "security_sessions": FakeCollection("security_sessions"),
        "security_login_history": FakeCollection("security_login_history"),
        "security_settings": FakeCollection("security_settings"),
    })

    # Clear memory OTP store before each test
    otp_service._in_memory_otps.clear()
    otp_service._last_otp_request_time.clear()

    app.dependency_overrides[get_vendors_collection] = lambda: vendors_col
    app.state.database = fake_db

    # Force redis to None during tests to ensure fast deterministic in-memory execution
    with patch("app.services.otp_service.get_redis_client", return_value=None):
        client = TestClient(app)
        try:
            yield client, vendors_col, fake_db
        finally:
            app.dependency_overrides.clear()
            app.state.database = None
            otp_service._in_memory_otps.clear()
            otp_service._last_otp_request_time.clear()


def test_send_signup_otp_success(auth_env):
    client, vendors_col, _ = auth_env

    with patch("app.modules.auth.router.send_signup_otp_email", return_value=True) as mock_email:
        res = client.post(
            "/api/v1/auth/signup/send-otp",
            json={"email": "partner@wavygo.in", "name": "Partner One"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "sent to your email" in data["message"].lower()
        mock_email.assert_called_once()


def test_send_signup_otp_rate_limit(auth_env):
    client, _, _ = auth_env

    with patch("app.modules.auth.router.send_signup_otp_email", return_value=True):
        res1 = client.post(
            "/api/v1/auth/signup/send-otp",
            json={"email": "cooldown@wavygo.in"},
        )
        assert res1.status_code == 200

        # Immediate second request should be rate-limited with 429
        res2 = client.post(
            "/api/v1/auth/signup/send-otp",
            json={"email": "cooldown@wavygo.in"},
        )
        assert res2.status_code == 429
        assert "wait" in res2.json()["detail"].lower()


def test_send_signup_otp_existing_vendor_fails(auth_env):
    client, vendors_col, _ = auth_env

    vendors_col.insert_one({
        "email": "existing@wavygo.in",
        "email_normalized": "existing@wavygo.in",
        "is_active": True,
        "password_hash": hash_password("Secret12345!"),
    })

    res = client.post(
        "/api/v1/auth/signup/send-otp",
        json={"email": "existing@wavygo.in"},
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"].lower()


def test_signup_invalid_otp_fails(auth_env):
    client, _, _ = auth_env

    res = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newvendor@wavygo.in",
            "password": "SecurePassword123!",
            "otp": "999999",
            "business_name": "Fast Bikes Ltd",
        },
    )
    assert res.status_code == 400
    assert "invalid or expired" in res.json()["detail"].lower()


def test_signup_success_flow(auth_env):
    client, vendors_col, fake_db = auth_env
    email = "newvendor@wavygo.in"

    with patch("app.modules.auth.router.send_signup_otp_email", return_value=True):
        client.post("/api/v1/auth/signup/send-otp", json={"email": email, "name": "New Vendor"})

    # Retrieve generated OTP from memory store
    stored = otp_service._in_memory_otps.get(email)
    assert stored is not None
    stored_otp = stored[0]
    assert len(stored_otp) == 6

    with patch("app.modules.auth.router.send_welcome_email", return_value=True) as mock_welcome:
        signup_res = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "otp": stored_otp,
                "business_name": "Fast Bikes Ltd",
                "owner_name": "New Vendor",
                "phone": "+91 99887 76655",
            },
        )
        assert signup_res.status_code == 201
        token_data = signup_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        mock_welcome.assert_called_once()

    # Vendor should now exist in collection
    created = vendors_col.find_one({"email_normalized": email})
    assert created is not None
    assert created["business_name"] == "Fast Bikes Ltd"
    assert created["is_active"] is True
    assert created["email_verified"] is True

    # Standard login without OTP should work for this new vendor
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
