from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.modules.auth.security import get_vendors_collection, hash_password


TEST_SECRET = "test-only-secret-key-with-at-least-32-bytes"
PASSWORD = "VendorOneSecurePassword!"
VENDOR_ID = ObjectId()


class FakeVendorsCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {
            VENDOR_ID: {
                "_id": VENDOR_ID,
                "email": "vendor@wavygo.com",
                "email_normalized": "vendor@wavygo.com",
                "password_hash": hash_password(PASSWORD),
                "business_name": "GoRides Bangalore Fleet Hub",
                "owner_name": "Garv Agarwal",
                "phone": "+91 98765 43210",
                "address": "100ft Road, Indiranagar, Bengaluru",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560038",
                "gstin": "29AABCU9603R1ZM",
                "is_active": True,
                "plan": "Growth",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        }

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for vendor in self.documents.values():
            if all(vendor.get(k) == v for k, v in query.items()):
                return deepcopy(vendor)
        return None

    def find(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for vendor in self.documents.values():
            if all(vendor.get(k) == v for k, v in query.items()):
                results.append(deepcopy(vendor))
        return results

    def update_one(self, query: dict[str, Any], changes: dict[str, Any]) -> Any:
        for vendor in self.documents.values():
            if all(vendor.get(k) == v for k, v in query.items()):
                vendor.update(deepcopy(changes.get("$set", {})))
                return type("UpdateResult", (), {"matched_count": 1})()
        return type("UpdateResult", (), {"matched_count": 0})()


@pytest.fixture
def tenants_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "mongodb_uri", None)
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_SECRET))
    monkeypatch.setattr(settings, "jwt_access_token_minutes", 30)

    vendors = FakeVendorsCollection()
    app.dependency_overrides[get_vendors_collection] = lambda: vendors

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "vendor@wavygo.com", "password": PASSWORD},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        yield client, vendors

    app.dependency_overrides.clear()


def test_get_current_tenant_profile(tenants_api):
    client, _ = tenants_api
    response = client.get("/api/v1/tenants/current")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["id"] == str(VENDOR_ID)
    assert data["businessName"] == "GoRides Bangalore Fleet Hub"
    assert data["email"] == "vendor@wavygo.com"
    assert data["status"] == "Active"
    assert "rentalRules" in data
    assert data["rentalRules"]["currency"] == "INR"


def test_update_current_tenant_profile(tenants_api):
    client, _ = tenants_api
    update_payload = {
        "businessName": "GoRides Karnataka Super Hub",
        "phone": "+91 91234 56789",
        "city": "Bengaluru Central",
        "rentalRules": {
            "minimumRentalHours": 48,
            "advanceBookingDays": 60,
            "defaultSecurityDeposit": 3000.0,
            "cancellationHours": 12,
            "currency": "INR",
        },
    }

    response = client.put("/api/v1/tenants/current", json=update_payload)
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["businessName"] == "GoRides Karnataka Super Hub"
    assert data["phone"] == "+91 91234 56789"
    assert data["city"] == "Bengaluru Central"
    assert data["rentalRules"]["minimumRentalHours"] == 48
    assert data["rentalRules"]["defaultSecurityDeposit"] == 3000.0


def test_tenant_stats(tenants_api):
    client, _ = tenants_api
    response = client.get("/api/v1/tenants/stats")
    assert response.status_code == 200, response.text

    stats = response.json()
    assert "vehicles" in stats
    assert "customers" in stats
    assert "active_bookings" in stats
    assert "staff_members" in stats
    assert stats["tenant_id"] == str(VENDOR_ID)


def test_get_tenant_by_id(tenants_api):
    client, _ = tenants_api
    response = client.get(f"/api/v1/tenants/{VENDOR_ID}")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(VENDOR_ID)


def test_get_tenant_invalid_id_returns_400(tenants_api):
    client, _ = tenants_api
    response = client.get("/api/v1/tenants/not-an-object-id")
    assert response.status_code == 400


def test_get_tenant_missing_returns_404(tenants_api):
    client, _ = tenants_api
    missing_id = ObjectId()
    response = client.get(f"/api/v1/tenants/{missing_id}")
    assert response.status_code == 404


def test_unauthenticated_tenant_access(tenants_api):
    client, _ = tenants_api
    client.headers.pop("Authorization", None)
    response = client.get("/api/v1/tenants/current")
    assert response.status_code == 401

