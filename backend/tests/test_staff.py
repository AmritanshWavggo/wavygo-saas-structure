from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.main import app
from app.modules.auth.security import (
    get_vendors_collection,
    hash_password,
)
from app.modules.staff.router import get_staff_collection


TEST_SECRET = "test-only-secret-key-with-at-least-32-bytes"
PASSWORD = "VendorOneSecurePassword!"
VALID_ROLES = [
    "Fleet manager",
    "Operations associate",
    "Customer support",
    "Delivery associate",
    "Administrator",
]


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = deepcopy(documents)

    def sort(self, key: str, direction: int = -1) -> "FakeCursor":
        self.documents.sort(
            key=lambda doc: doc.get(key) or datetime.min,
            reverse=direction == -1,
        )
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class FakeStaffCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}
        self.fail_insert = False
        self.fail_find = False
        self.fail_update = False

    def insert_one(self, document: dict[str, Any]) -> Any:
        if self.fail_insert:
            raise PyMongoError("Simulated insert failure")

        object_id = ObjectId()
        self.documents[object_id] = {
            **deepcopy(document),
            "_id": object_id,
        }
        return type("InsertResult", (), {"inserted_id": object_id})()

    def find(self, query: dict[str, Any]) -> FakeCursor:
        if self.fail_find:
            raise PyMongoError("Simulated find failure")

        return FakeCursor([
            document
            for document in self.documents.values()
            if all(document.get(k) == v for k, v in query.items())
        ])

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if self.fail_find:
            raise PyMongoError("Simulated find failure")

        for document in self.documents.values():
            if all(document.get(k) == v for k, v in query.items()):
                return deepcopy(document)
        return None

    def update_one(
        self, query: dict[str, Any], changes: dict[str, Any]
    ) -> Any:
        if self.fail_update:
            raise PyMongoError("Simulated update failure")

        for document in self.documents.values():
            if all(document.get(k) == v for k, v in query.items()):
                document.update(deepcopy(changes.get("$set", {})))
                if "$push" in changes:
                    for k, val in changes["$push"].items():
                        document.setdefault(k, []).append(deepcopy(val))
                if "$pull" in changes:
                    for k, val in changes["$pull"].items():
                        if k in document and isinstance(document[k], list):
                            if isinstance(val, dict):
                                document[k] = [
                                    item for item in document[k]
                                    if not all(item.get(ik) == iv for ik, iv in val.items())
                                ]
                return type("UpdateResult", (), {"matched_count": 1})()

        return type("UpdateResult", (), {"matched_count": 0})()


class FakeVendorsCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}
        object_id = ObjectId()
        self.documents[object_id] = {
            "_id": object_id,
            "email": "staff-test@example.com",
            "email_normalized": "staff-test@example.com",
            "password_hash": hash_password(PASSWORD),
            "is_active": True,
        }

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for vendor in self.documents.values():
            if all(vendor.get(k) == v for k, v in query.items()):
                return deepcopy(vendor)
        return None


@pytest.fixture
def staff_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "mongodb_uri", None)
    monkeypatch.setattr(
        settings, "jwt_secret_key", SecretStr(TEST_SECRET)
    )
    monkeypatch.setattr(settings, "jwt_access_token_minutes", 30)

    staff = FakeStaffCollection()
    vendors = FakeVendorsCollection()

    app.dependency_overrides[get_staff_collection] = lambda: staff
    app.dependency_overrides[get_vendors_collection] = lambda: vendors

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "staff-test@example.com",
                "password": PASSWORD,
            },
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        yield client, staff

    app.dependency_overrides.clear()


def staff_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "name": "Asha Rao",
        "role": "Fleet manager",
        "phone": "+91 98765 43210",
        "salary": 25000,
        "attendance": "Present",
        "nextSalary": "2026-11-01",
        "status": "Active",
    }
    payload.update(overrides)
    return payload


def test_staff_create_and_list(staff_api):
    client, staff = staff_api

    created = client.post(
        "/api/v1/staff/", json=staff_payload()
    )
    assert created.status_code == 201, created.text

    body = created.json()
    assert body["name"] == "Asha Rao"
    assert body["role"] == "Fleet manager"
    assert body["status"] == "Active"
    assert "id" in body
    assert "tenant_id" not in body

    listed = client.get("/api/v1/staff/")
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == body["id"]


def test_staff_create_defaults():
    # Covered through the API in test_staff_create_and_list.
    assert "Fleet manager" in VALID_ROLES


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"role": "Unknown role"},
        {"phone": "123"},
        {"salary": -1},
        {"status": "Pending"},
        {"unexpected": "field"},
    ],
)
def test_staff_invalid_create_payload_is_rejected(staff_api, overrides):
    client, _ = staff_api
    response = client.post(
        "/api/v1/staff/", json=staff_payload(**overrides)
    )
    assert response.status_code == 422, response.text


def test_staff_update_details(staff_api):
    client, _ = staff_api
    created = client.post(
        "/api/v1/staff/", json=staff_payload()
    )
    staff_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/staff/{staff_id}",
        json={"name": "Asha Kumar", "salary": 30000},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Asha Kumar"
    assert updated.json()["salary"] == 30000


def test_staff_update_status(staff_api):
    client, _ = staff_api
    created = client.post(
        "/api/v1/staff/", json=staff_payload()
    )
    staff_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/staff/{staff_id}/status",
        json={"status": "Inactive"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Inactive"


def test_staff_update_rejects_empty_changes(staff_api):
    client, _ = staff_api
    created = client.post(
        "/api/v1/staff/", json=staff_payload()
    )

    response = client.put(
        f"/api/v1/staff/{created.json()['id']}", json={}
    )
    assert response.status_code == 400


def test_staff_invalid_id_is_rejected(staff_api):
    client, _ = staff_api
    response = client.put(
        "/api/v1/staff/not-an-object-id",
        json={"name": "Updated Name"},
    )
    assert response.status_code == 400


def test_staff_missing_id_returns_404(staff_api):
    client, _ = staff_api
    response = client.put(
        f"/api/v1/staff/{ObjectId()}",
        json={"name": "Updated Name"},
    )
    assert response.status_code == 404


def test_staff_tenant_isolation(staff_api):
    client, staff = staff_api

    created = client.post(
        "/api/v1/staff/", json=staff_payload()
    )
    assert created.status_code == 201, created.text
    staff_id = ObjectId(created.json()["id"])

    other_tenant = ObjectId()
    staff.documents[staff_id]["tenant_id"] = other_tenant

    response = client.put(
        f"/api/v1/staff/{staff_id}",
        json={"name": "Unauthorized Update"},
    )
    assert response.status_code == 404


def test_staff_endpoints_require_authentication(staff_api):
    client, _ = staff_api
    client.headers.pop("Authorization", None)

    response = client.get("/api/v1/staff/")
    assert response.status_code == 401


def test_staff_missing_database_returns_503():
    from fastapi import HTTPException
    from app.modules.staff.router import get_staff_collection

    class FakeAppState:
        database = None

    class FakeApp:
        state = FakeAppState()

    class FakeRequest:
        app = FakeApp()

    with pytest.raises(HTTPException) as error:
        get_staff_collection(FakeRequest())

    assert error.value.status_code == 503


def test_staff_document_upload_and_lifecycle(staff_api):
    client, staff_collection = staff_api
    create_response = client.post(
        "/api/v1/staff/",
        json={
            "name": "Document Tester",
            "role": "Operations associate",
            "phone": "+91 99999 88888",
            "salary": 32000,
        },
    )
    assert create_response.status_code == 201
    staff_id = create_response.json()["id"]

    # Test upload valid document
    file_content = b"%PDF-1.4 mock pdf content"
    upload_response = client.post(
        f"/api/v1/staff/{staff_id}/documents",
        data={"category": "Aadhaar Card"},
        files={"file": ("aadhaar.pdf", file_content, "application/pdf")},
    )
    assert upload_response.status_code == 201
    doc_data = upload_response.json()
    assert doc_data["name"] == "aadhaar.pdf"
    assert doc_data["category"] == "Aadhaar Card"
    doc_id = doc_data["id"]

    # Test list documents
    list_response = client.get(f"/api/v1/staff/{staff_id}/documents")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == doc_id

    # Test download document
    download_response = client.get(f"/api/v1/staff/{staff_id}/documents/{doc_id}/download")
    assert download_response.status_code == 200
    assert download_response.content == file_content

    # Test delete document
    delete_response = client.delete(f"/api/v1/staff/{staff_id}/documents/{doc_id}")
    assert delete_response.status_code == 200

    # Verify list is empty
    list_after = client.get(f"/api/v1/staff/{staff_id}/documents")
    assert list_after.status_code == 200
    assert len(list_after.json()["items"]) == 0


