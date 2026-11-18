from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pyotp
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.modules.auth.security import get_vendors_collection, hash_password


TEST_SECRET = "test-only-secret-key-with-at-least-32-bytes"
PASSWORD = "VendorOneSecurePassword!42"
VENDOR_ID = ObjectId()


class FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = list(docs)

    def sort(self, key: str, direction: int = -1) -> "FakeCursor":
        self.docs.sort(
            key=lambda d: d.get(key) or datetime.min,
            reverse=(direction == -1),
        )
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(deepcopy(self.docs))

    def __len__(self):
        return len(self.docs)


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

    def count_documents(self, filt: dict[str, Any] | None = None) -> int:
        return len(self.find(filt))

    def _matches(self, doc: dict[str, Any], filt: dict[str, Any] | None) -> bool:
        if not filt:
            return True
        for k, v in filt.items():
            if k.startswith("$"):
                continue
            if isinstance(v, dict):
                val = doc.get(k)
                for op, expected in v.items():
                    if op == "$gt" and (val is None or not (val > expected)):
                        return False
                    if op == "$gte" and (val is None or not (val >= expected)):
                        return False
                    if op == "$lt" and (val is None or not (val < expected)):
                        return False
                    if op == "$lte" and (val is None or not (val <= expected)):
                        return False
            elif doc.get(k) != v:
                return False
        return True

    def find(self, filt: dict[str, Any] | None = None) -> FakeCursor:
        matched = [deepcopy(d) for d in self.docs if self._matches(d, filt)]
        return FakeCursor(matched)

    def find_one(self, filt: dict[str, Any] | None = None) -> dict[str, Any] | None:
        for d in self.docs:
            if self._matches(d, filt):
                return deepcopy(d)
        return None

    def update_one(
        self, filt: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> Any:
        for d in self.docs:
            if self._matches(d, filt):
                if "$set" in update:
                    d.update(deepcopy(update["$set"]))
                if "$unset" in update:
                    for k in update["$unset"]:
                        d.pop(k, None)
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()

        if upsert:
            new_doc = deepcopy(filt)
            if "$set" in update:
                new_doc.update(deepcopy(update["$set"]))
            if "$setOnInsert" in update:
                new_doc.update(deepcopy(update["$setOnInsert"]))
            if "_id" not in new_doc:
                new_doc["_id"] = ObjectId()
            self.docs.append(new_doc)
            return type(
                "UpdateResult",
                (),
                {"matched_count": 0, "modified_count": 1, "upserted_id": new_doc["_id"]},
            )()

        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    def update_many(self, filt: dict[str, Any], update: dict[str, Any]) -> Any:
        count = 0
        for d in self.docs:
            if self._matches(d, filt):
                count += 1
                if "$set" in update:
                    d.update(deepcopy(update["$set"]))
                if "$unset" in update:
                    for k in update["$unset"]:
                        d.pop(k, None)
        return type("UpdateResult", (), {"matched_count": count, "modified_count": count})()

    def delete_many(self, filt: dict[str, Any]) -> Any:
        initial = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filt)]
        return type("DeleteResult", (), {"deleted_count": initial - len(self.docs)})()


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]

    def __getattr__(self, name: str) -> FakeCollection:
        return self[name]


@pytest.fixture
def security_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "mongodb_uri", None)
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_SECRET))
    monkeypatch.setattr(settings, "jwt_access_token_minutes", 30)

    db = FakeDatabase()
    vendor_doc = {
        "_id": VENDOR_ID,
        "email": "vendor@wavygo.com",
        "email_normalized": "vendor@wavygo.com",
        "password_hash": hash_password(PASSWORD),
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": datetime.now(timezone.utc),
    }
    db["vendors"].insert_one(vendor_doc)

    app.dependency_overrides[get_vendors_collection] = lambda: db["vendors"]

    with TestClient(app) as client:
        app.state.database = db
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "vendor@wavygo.com", "password": PASSWORD},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        yield client, db

    app.dependency_overrides.clear()
    app.state.database = None


def test_security_overview(security_api):
    client, db = security_api
    response = client.get("/api/v1/security/overview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "active_sessions" in data
    assert "failed_logins_last_7_days" in data
    assert "unresolved_alerts" in data
    assert "two_factor_enabled" in data
    assert data["active_sessions"] >= 1


def test_security_sessions_list_and_revoke(security_api):
    client, db = security_api
    # Insert a second session to revoke without revoking our active one
    other_session_id = ObjectId()
    db["security_sessions"].insert_one({
        "_id": other_session_id,
        "vendor_id": VENDOR_ID,
        "ip_address": "127.0.0.1",
        "user_agent": "OtherBrowser",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "revoked_at": None,
    })

    response = client.get("/api/v1/security/sessions")
    assert response.status_code == 200, response.text
    sessions = response.json()
    assert len(sessions) >= 2

    # Revoke the other session
    revoke_resp = client.delete(f"/api/v1/security/sessions/{other_session_id}")
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["message"] == "Session revoked."

    # Revoking already revoked session should return 404
    second_revoke = client.delete(f"/api/v1/security/sessions/{other_session_id}")
    assert second_revoke.status_code == 404


def test_security_revoke_all(security_api):
    client, db = security_api
    response = client.post("/api/v1/security/sessions/revoke-all")
    assert response.status_code == 200
    assert "revoked_count" in response.json()

    # Subsequent request with now-revoked session should return 401
    assert client.get("/api/v1/security/overview").status_code == 401


def test_security_login_history(security_api):
    client, db = security_api
    response = client.get("/api/v1/security/login-history")
    assert response.status_code == 200
    history = response.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    assert history[0]["success"] is True


def test_security_audit_logs(security_api):
    client, db = security_api
    # Trigger an audit action without revoking current session
    client.put("/api/v1/security/settings", json={"login_alerts": False})
    response = client.get("/api/v1/security/audit-logs")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert any("security.settings_updated" in log["action"] for log in logs)


def test_security_alerts_and_resolve(security_api):
    client, db = security_api
    # Insert a test alert
    alert_id = ObjectId()
    db["security_events"].insert_one({
        "_id": alert_id,
        "vendor_id": VENDOR_ID,
        "type": "new_device",
        "severity": "warning",
        "message": "New device detected",
        "resolved": False,
        "created_at": datetime.now(timezone.utc),
    })

    alerts_resp = client.get("/api/v1/security/alerts")
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert any(a["id"] == str(alert_id) for a in alerts)

    resolve_resp = client.post(f"/api/v1/security/alerts/{alert_id}/resolve")
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["message"] == "Alert resolved."


def test_security_settings_get_and_update(security_api):
    client, db = security_api
    get_resp = client.get("/api/v1/security/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "login_alerts" in data
    assert "new_device_alerts" in data

    put_resp = client.put(
        "/api/v1/security/settings",
        json={"login_alerts": False, "new_device_alerts": False},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["login_alerts"] is False
    assert updated["new_device_alerts"] is False


def test_security_change_password(security_api):
    client, db = security_api
    new_password = "BrandNewSecurePassword!99"

    # Incorrect current password should fail
    fail_resp = client.post(
        "/api/v1/security/change-password",
        json={
            "current_password": "WrongPassword!123",
            "new_password": new_password,
        },
    )
    assert fail_resp.status_code == 400

    # Same password should fail
    same_resp = client.post(
        "/api/v1/security/change-password",
        json={
            "current_password": PASSWORD,
            "new_password": PASSWORD,
        },
    )
    assert same_resp.status_code == 400

    # Successful change
    success_resp = client.post(
        "/api/v1/security/change-password",
        json={
            "current_password": PASSWORD,
            "new_password": new_password,
        },
    )
    assert success_resp.status_code == 200


def test_security_2fa_flow(security_api):
    client, db = security_api
    # Setup 2FA
    setup_resp = client.post("/api/v1/security/2fa/setup")
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]
    assert "otpauth_uri" in setup_resp.json()

    # Enable with valid code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    enable_resp = client.post(
        "/api/v1/security/2fa/enable", json={"code": valid_code}
    )
    assert enable_resp.status_code == 200
    assert enable_resp.json()["message"] == "Two-factor authentication enabled."

    # Disable with valid code
    disable_code = totp.now()
    disable_resp = client.post(
        "/api/v1/security/2fa/disable", json={"code": disable_code}
    )
    assert disable_resp.status_code == 200
    assert "disabled" in disable_resp.json()["message"]


def test_settings_router_endpoints(security_api):
    client, db = security_api
    resp_overview = client.get("/api/v1/settings/overview")
    assert resp_overview.status_code == 200
    resp_security = client.get("/api/v1/settings/security")
    assert resp_security.status_code == 200
    resp_base = client.get("/api/v1/settings")
    assert resp_base.status_code == 200


def test_unauthenticated_security_access(security_api):
    client, _ = security_api
    client.headers.pop("Authorization", None)
    response = client.get("/api/v1/security/overview")
    assert response.status_code == 401
