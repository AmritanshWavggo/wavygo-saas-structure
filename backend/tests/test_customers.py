from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.config import settings
from app.main import app
from app.modules.auth import reset_password
from app.modules.auth.security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    get_vendors_collection,
    hash_password,
    verify_password,
)
from app.modules.customers.router import get_customers_collection

TEST_SECRET = "test-only-secret-key-with-at-least-32-bytes"
VENDOR_ONE_PASSWORD = "VendorOneSecurePassword!"
VENDOR_TWO_PASSWORD = "VendorTwoSecurePassword!"


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(
        self, keys: str | list[tuple[str, int]], direction: int | None = None
    ) -> "FakeCursor":
        sort_keys = [(keys, direction or 1)] if isinstance(keys, str) else keys
        for key, key_direction in reversed(sort_keys):
            self.documents.sort(
                key=lambda document: document.get(key),
                reverse=key_direction == DESCENDING,
            )
        return self

    def skip(self, count: int) -> "FakeCursor":
        self.documents = self.documents[count:]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.documents = self.documents[:count]
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.documents)


class FakeCustomersCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}

    def insert_one(self, document: dict[str, Any]) -> Any:
        assert isinstance(document.get("tenant_id"), ObjectId)
        for existing in self.documents.values():
            same_tenant = existing.get("tenant_id") == document.get("tenant_id")
            same_phone = existing.get("phone_normalized") == document.get(
                "phone_normalized"
            )
            same_email = (
                document.get("email") is not None
                and existing.get("email") == document.get("email")
            )
            if same_tenant and (same_phone or same_email):
                raise DuplicateKeyError("Duplicate customer field.")
        object_id = ObjectId()
        self.documents[object_id] = {**document, "_id": object_id}
        return type("InsertResult", (), {"inserted_id": object_id})()

    def find(self, query: dict[str, Any]) -> FakeCursor:
        assert "tenant_id" in query
        return FakeCursor(
            [
                document
                for document in self.documents.values()
                if all(document.get(key) == value for key, value in query.items())
            ]
        )

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        assert "tenant_id" in query
        document = self.documents.get(query["_id"])
        if document is None or document.get("tenant_id") != query["tenant_id"]:
            return None
        return document

    def count_documents(self, query: dict[str, Any]) -> int:
        assert "tenant_id" in query
        return sum(
            all(document.get(key) == value for key, value in query.items())
            for document in self.documents.values()
        )

    def update_one(self, query: dict[str, Any], changes: dict[str, Any]) -> Any:
        assert "tenant_id" in query
        document = self.documents.get(query["_id"])
        if document is None or document.get("tenant_id") != query["tenant_id"]:
            return type("UpdateResult", (), {"matched_count": 0})()
        for existing_id, existing in self.documents.items():
            if existing_id != query["_id"] and existing.get("tenant_id") == query[
                "tenant_id"
            ] and (
                (
                    "phone_normalized" in changes["$set"]
                    and existing.get("phone_normalized")
                    == changes["$set"]["phone_normalized"]
                )
                or (
                    "email" in changes["$set"]
                    and existing.get("email") == changes["$set"]["email"]
                )
            ):
                raise DuplicateKeyError("Duplicate customer field.")
        document.update(changes["$set"])
        if "$unset" in changes:
            for field in changes["$unset"]:
                document.pop(field, None)
        return type("UpdateResult", (), {"matched_count": 1})()

    def delete_one(self, query: dict[str, Any]) -> Any:
        assert "tenant_id" in query
        document = self.documents.get(query["_id"])
        if document is None or document.get("tenant_id") != query["tenant_id"]:
            return type("DeleteResult", (), {"deleted_count": 0})()
        del self.documents[query["_id"]]
        return type("DeleteResult", (), {"deleted_count": 1})()


class FakeVendorsCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}

    def add_vendor(self, email: str, password: str) -> ObjectId:
        object_id = ObjectId()
        self.documents[object_id] = {
            "_id": object_id,
            "email": email,
            "email_normalized": email,
            "password_hash": hash_password(password),
            "is_active": True,
        }
        return object_id

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next(
            (
                vendor
                for vendor in self.documents.values()
                if all(vendor.get(key) == value for key, value in query.items())
            ),
            None,
        )


@dataclass
class ApiTestContext:
    client: TestClient
    customers: FakeCustomersCollection
    vendors: FakeVendorsCollection
    vendor_ids: dict[str, ObjectId]
    tokens: dict[str, str]


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiTestContext]:
    monkeypatch.setattr(settings, "mongodb_uri", None)
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_SECRET))
    monkeypatch.setattr(settings, "jwt_access_token_minutes", 30)
    customers = FakeCustomersCollection()
    vendors = FakeVendorsCollection()
    vendor_ids = {
        "one": vendors.add_vendor("one@example.com", VENDOR_ONE_PASSWORD),
        "two": vendors.add_vendor("two@example.com", VENDOR_TWO_PASSWORD),
    }
    app.dependency_overrides[get_customers_collection] = lambda: customers
    app.dependency_overrides[get_vendors_collection] = lambda: vendors

    with TestClient(app) as client:
        tokens: dict[str, str] = {}
        for label, email, password in (
            ("one", "one@example.com", VENDOR_ONE_PASSWORD),
            ("two", "two@example.com", VENDOR_TWO_PASSWORD),
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 200
            tokens[label] = response.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {tokens['one']}"})
        yield ApiTestContext(client, customers, vendors, vendor_ids, tokens)

    app.dependency_overrides.clear()


def test_customer_crud_and_pagination(api: ApiTestContext) -> None:
    client = api.client
    created = client.post(
        "/api/v1/customers/",
        json={
            "name": "  Maya Patel ",
            "phone": "+91 98765 43210",
            "email": "MAYA@example.com",
            "status": "Verified",
        },
    )

    assert created.status_code == 201
    customer = created.json()
    assert customer["name"] == "Maya Patel"
    assert customer["email"] == "maya@example.com"
    assert customer["bookings"] == customer["active"] == 0
    customer_id = customer["id"]

    updated = client.put(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "+91 98765 00000"},
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+91 98765 00000"

    listed = client.get("/api/v1/customers/?skip=0&limit=1")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == customer_id

    retrieved = client.get(f"/api/v1/customers/{customer_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == customer_id

    deleted = client.delete(f"/api/v1/customers/{customer_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/customers/{customer_id}").status_code == 404


def test_customer_phone_and_email_uniqueness_is_per_tenant(
    api: ApiTestContext,
) -> None:
    client = api.client
    customer = {
        "name": "Vendor One Customer",
        "phone": "+1 415 555 0134",
        "email": "shared@example.com",
    }
    created_one = client.post("/api/v1/customers/", json=customer)
    assert created_one.status_code == 201

    vendor_two_headers = {"Authorization": f"Bearer {api.tokens['two']}"}
    created_two = client.post(
        "/api/v1/customers/",
        json={**customer, "name": "Vendor Two Customer"},
        headers=vendor_two_headers,
    )
    assert created_two.status_code == 201
    assert created_two.json()["id"] != created_one.json()["id"]

    same_tenant_phone = client.post(
        "/api/v1/customers/",
        json={
            "name": "Duplicate Phone",
            "phone": "14155550134",
            "email": "other@example.com",
        },
    )
    same_tenant_email = client.post(
        "/api/v1/customers/",
        json={
            "name": "Duplicate Email",
            "phone": "14155550135",
            "email": "SHARED@example.com",
        },
    )
    assert same_tenant_phone.status_code == 409
    assert same_tenant_email.status_code == 409

    cross_tenant_update = client.put(
        f"/api/v1/customers/{created_one.json()['id']}",
        json={"phone": "14155550134", "email": "shared@example.com"},
    )
    assert cross_tenant_update.status_code == 200


def test_customer_list_status_filter_and_pagination(api: ApiTestContext) -> None:
    client = api.client
    for index, customer_status in enumerate(("Review", "Verified", "Verified")):
        response = client.post(
            "/api/v1/customers/",
            json={
                "name": f"Customer {index}",
                "phone": f"98765432{index:02d}",
                "status": customer_status,
            },
        )
        assert response.status_code == 201

    filtered = client.get("/api/v1/customers/?status=Verified&skip=1&limit=1")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["items"][0]["status"] == "Verified"
    assert filtered.json()["skip"] == 1
    assert filtered.json()["limit"] == 1
    assert client.get("/api/v1/customers/?status=Unknown").status_code == 422


def test_legacy_customer_without_tenant_is_not_exposed(
    api: ApiTestContext,
) -> None:
    legacy_id = ObjectId()
    api.customers.documents[legacy_id] = {
        "_id": legacy_id,
        "name": "Unassigned legacy record",
        "phone": "9876543210",
        "phone_normalized": "9876543210",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    listed = api.client.get("/api/v1/customers/")
    retrieved = api.client.get(f"/api/v1/customers/{legacy_id}")

    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert retrieved.status_code == 404


def test_customer_collection_dependency_does_not_create_indexes() -> None:
    customers = FakeCustomersCollection()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(database={"customers": customers})
        )
    )

    assert get_customers_collection(request) is customers


def test_customer_validation_and_duplicate_fields(api: ApiTestContext) -> None:
    client = api.client
    invalid = client.post(
        "/api/v1/customers/",
        json={"name": " ", "phone": "bad", "email": "not-an-email"},
    )
    assert invalid.status_code == 422

    customer = {"name": "Maya Patel", "phone": "9876543210", "email": "maya@example.com"}
    assert client.post("/api/v1/customers/", json=customer).status_code == 201
    duplicate = client.post(
        "/api/v1/customers/",
        json={"name": "Another Customer", "phone": "98765-43210"},
    )
    assert duplicate.status_code == 409

    empty_update = client.put(f"/api/v1/customers/{ObjectId()}", json={})
    assert empty_update.status_code == 422
    null_name_update = client.put(
        f"/api/v1/customers/{ObjectId()}", json={"name": None}
    )
    assert null_name_update.status_code == 422
    spoofed_update = client.put(
        f"/api/v1/customers/{ObjectId()}",
        json={"tenant_id": str(api.vendor_ids["two"])},
    )
    assert spoofed_update.status_code == 422
    assert client.get("/api/v1/customers/?limit=101").status_code == 422


def test_invalid_and_missing_customer_ids(api: ApiTestContext) -> None:
    client = api.client
    assert client.get("/api/v1/customers/not-an-object-id").status_code == 400
    assert client.get(f"/api/v1/customers/{ObjectId()}").status_code == 404
    assert client.delete(f"/api/v1/customers/{ObjectId()}").status_code == 404


def test_database_errors_return_service_unavailable(api: ApiTestContext) -> None:
    class UnavailableCollection:
        def insert_one(self, _document: dict[str, Any]) -> None:
            raise PyMongoError("MongoDB is unavailable.")

    app.dependency_overrides[get_customers_collection] = lambda: UnavailableCollection()
    response = api.client.post(
        "/api/v1/customers/",
        json={"name": "Maya Patel", "phone": "9876543210"},
    )
    assert response.status_code == 503


def test_update_customer_duplicate_phone_returns_conflict(api: ApiTestContext) -> None:
    client = api.client
    first = client.post(
        "/api/v1/customers/",
        json={"name": "Customer One", "phone": "9876543210"},
    )
    second = client.post(
        "/api/v1/customers/",
        json={"name": "Customer Two", "phone": "9876543211"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.put(
        f"/api/v1/customers/{first.json()['id']}",
        json={"phone": "9876543211"},
    )
    assert response.status_code == 409


def test_update_customer_phone_used_by_different_tenant_succeeds(
    api: ApiTestContext,
) -> None:
    client = api.client
    vendor_two_headers = {"Authorization": f"Bearer {api.tokens['two']}"}

    vendor_one_customer = client.post(
        "/api/v1/customers/",
        json={
            "name": "Vendor One Customer",
            "phone": "9876543210",
            "email": "one-phone@example.com",
        },
    )
    vendor_two_customer = client.post(
        "/api/v1/customers/",
        json={
            "name": "Vendor Two Customer",
            "phone": "9876543211",
            "email": "two-phone@example.com",
        },
        headers=vendor_two_headers,
    )
    assert vendor_one_customer.status_code == 201
    assert vendor_two_customer.status_code == 201

    updated = client.put(
        f"/api/v1/customers/{vendor_one_customer.json()['id']}",
        json={"phone": "9876543211"},
    )

    assert updated.status_code == 200
    assert updated.json()["phone"] == "9876543211"
    assert api.customers.documents[ObjectId(vendor_two_customer.json()["id"])][
        "tenant_id"
    ] == api.vendor_ids["two"]
    assert api.customers.documents[ObjectId(vendor_two_customer.json()["id"])][
        "phone_normalized"
    ] == "9876543211"


def test_update_customer_email_used_by_different_tenant_succeeds(
    api: ApiTestContext,
) -> None:
    client = api.client
    vendor_two_headers = {"Authorization": f"Bearer {api.tokens['two']}"}

    vendor_one_customer = client.post(
        "/api/v1/customers/",
        json={
            "name": "Vendor One Customer",
            "phone": "9876543212",
            "email": "one-email@example.com",
        },
    )
    vendor_two_customer = client.post(
        "/api/v1/customers/",
        json={
            "name": "Vendor Two Customer",
            "phone": "9876543213",
            "email": "shared@example.com",
        },
        headers=vendor_two_headers,
    )
    assert vendor_one_customer.status_code == 201
    assert vendor_two_customer.status_code == 201

    updated = client.put(
        f"/api/v1/customers/{vendor_one_customer.json()['id']}",
        json={"email": "SHARED@example.com"},
    )

    assert updated.status_code == 200
    assert updated.json()["email"] == "shared@example.com"
    assert api.customers.documents[ObjectId(vendor_two_customer.json()["id"])][
        "tenant_id"
    ] == api.vendor_ids["two"]
    assert api.customers.documents[ObjectId(vendor_two_customer.json()["id"])][
        "email"
    ] == "shared@example.com"


def test_update_customer_email_used_by_same_tenant_returns_conflict(
    api: ApiTestContext,
) -> None:
    client = api.client
    first = client.post(
        "/api/v1/customers/",
        json={
            "name": "Customer One",
            "phone": "9876543214",
            "email": "first@example.com",
        },
    )
    second = client.post(
        "/api/v1/customers/",
        json={
            "name": "Customer Two",
            "phone": "9876543215",
            "email": "second@example.com",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    updated = client.put(
        f"/api/v1/customers/{first.json()['id']}",
        json={"email": "SECOND@example.com"},
    )

    assert updated.status_code == 409
    assert api.customers.documents[ObjectId(first.json()["id"])][
        "email"
    ] == "first@example.com"
    assert api.customers.documents[ObjectId(second.json()["id"])][
        "tenant_id"
    ] == api.vendor_ids["one"]
    assert api.customers.documents[ObjectId(second.json()["id"])][
        "email"
    ] == "second@example.com"


def test_update_customer_remove_email(api: ApiTestContext) -> None:
    client = api.client
    created = client.post(
        "/api/v1/customers/",
        json={
            "name": "Email Test",
            "phone": "9876543212",
            "email": "emailtest@example.com",
        },
    )
    assert created.status_code == 201

    response = client.put(
        f"/api/v1/customers/{created.json()['id']}",
        json={"email": None},
    )
    assert response.status_code == 200
    assert response.json()["email"] is None


def test_customer_endpoints_require_authentication(api: ApiTestContext) -> None:
    unauthenticated = {"Authorization": ""}
    customer_id = str(ObjectId())
    requests = (
        api.client.get("/api/v1/customers/", headers=unauthenticated),
        api.client.get(f"/api/v1/customers/{customer_id}", headers=unauthenticated),
        api.client.post(
            "/api/v1/customers/",
            json={"name": "Maya Patel", "phone": "9876543210"},
            headers=unauthenticated,
        ),
        api.client.put(
            f"/api/v1/customers/{customer_id}",
            json={"name": "Updated"},
            headers=unauthenticated,
        ),
        api.client.delete(
            f"/api/v1/customers/{customer_id}",
            headers=unauthenticated,
        ),
    )
    assert [response.status_code for response in requests] == [401] * 5


def test_invalid_token_is_rejected(api: ApiTestContext) -> None:
    response = api.client.get(
        "/api/v1/customers/",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


def test_customer_data_is_isolated_by_vendor(api: ApiTestContext) -> None:
    first_customer = api.client.post(
        "/api/v1/customers/",
        json={"name": "Vendor One Customer", "phone": "9876543210"},
    )
    assert first_customer.status_code == 201
    customer_id = first_customer.json()["id"]
    customer_object_id = ObjectId(customer_id)

    vendor_two_headers = {"Authorization": f"Bearer {api.tokens['two']}"}
    vendor_two_list = api.client.get(
        "/api/v1/customers/",
        headers=vendor_two_headers,
    )
    assert vendor_two_list.status_code == 200
    assert vendor_two_list.json()["total"] == 0
    assert vendor_two_list.json()["items"] == []
    assert api.client.get(
        f"/api/v1/customers/{customer_id}",
        headers=vendor_two_headers,
    ).status_code == 404
    assert api.client.put(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Unauthorized change"},
        headers=vendor_two_headers,
    ).status_code == 404
    assert api.client.delete(
        f"/api/v1/customers/{customer_id}",
        headers=vendor_two_headers,
    ).status_code == 404

    stored = api.customers.documents[customer_object_id]
    assert stored["tenant_id"] == api.vendor_ids["one"]
    assert stored["name"] == "Vendor One Customer"

    second_customer = api.client.post(
        "/api/v1/customers/",
        json={"name": "Vendor Two Customer", "phone": "9876543211"},
        headers=vendor_two_headers,
    )
    assert second_customer.status_code == 201
    assert second_customer.json()["id"] != customer_id
    assert api.client.get(
        "/api/v1/customers/",
        headers=vendor_two_headers,
    ).json()["total"] == 1


def test_request_cannot_choose_customer_tenant(api: ApiTestContext) -> None:
    response = api.client.post(
        "/api/v1/customers/",
        json={
            "name": "Spoof Attempt",
            "phone": "9876543213",
            "tenant_id": str(api.vendor_ids["two"]),
        },
    )
    assert response.status_code == 422


def test_login_rejects_incorrect_password(api: ApiTestContext) -> None:
    response = api.client.post(
        "/api/v1/auth/login",
        json={"email": "one@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


def test_login_normalizes_email(api: ApiTestContext) -> None:
    response = api.client.post(
        "/api/v1/auth/login",
        json={"email": " ONE@Example.com ", "password": VENDOR_ONE_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_inactive_vendor_and_expired_token_are_rejected(
    api: ApiTestContext,
) -> None:
    vendor_id = api.vendor_ids["one"]
    vendor = next(
        vendor for vendor in api.vendors.documents.values()
        if vendor["_id"] == vendor_id
    )
    vendor["is_active"] = False

    inactive_response = api.client.get(
        "/api/v1/customers/",
        headers={"Authorization": f"Bearer {api.tokens['one']}"},
    )
    login_response = api.client.post(
        "/api/v1/auth/login",
        json={"email": "one@example.com", "password": VENDOR_ONE_PASSWORD},
    )
    assert inactive_response.status_code == 401
    assert login_response.status_code == 401

    expired_token = jwt.encode(
        {
            "sub": str(api.vendor_ids["two"]),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "type": "access",
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    expired_response = api.client.get(
        "/api/v1/customers/",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired_response.status_code == 401


def test_password_reset_updates_only_matching_hash_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    password = "ReplacementPassword!42"

    class ResetCollection:
        def __init__(self) -> None:
            self.query: dict[str, Any] | None = None
            self.update: dict[str, Any] | None = None

        def update_one(
            self, query: dict[str, Any], update: dict[str, Any]
        ) -> Any:
            self.query = query
            self.update = update
            return type("UpdateResult", (), {"matched_count": 1})()

    class ResetClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    collection = ResetCollection()
    client = ResetClient()
    database = {"vendors": collection}
    prompts = iter([" Test@Gmail.com "])
    hidden_prompts = iter([password, password])

    def read_email(prompt: str) -> str:
        assert prompt == "Vendor email: "
        return next(prompts)

    def read_password(prompt: str) -> str:
        assert prompt in {
            "New password (12-128 characters): ",
            "Confirm new password: ",
        }
        return next(hidden_prompts)

    def get_test_database(provided_client: ResetClient) -> dict[str, ResetCollection]:
        assert provided_client is client
        return database

    monkeypatch.setattr("builtins.input", read_email)
    monkeypatch.setattr(reset_password.getpass, "getpass", read_password)
    monkeypatch.setattr(reset_password, "create_mongo_client", lambda: client)
    monkeypatch.setattr(reset_password, "get_database", get_test_database)

    assert reset_password.main() == 0

    assert collection.query == {"email_normalized": "test@gmail.com"}
    assert collection.update is not None
    assert set(collection.update) == {"$set"}
    assert set(collection.update["$set"]) == {"password_hash"}
    assert verify_password(password, collection.update["$set"]["password_hash"])
    assert client.closed
    assert capsys.readouterr().out.strip() == "Vendor password updated."


def test_password_reset_rejects_mismatch_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompts = iter(["test@gmail.com"])
    hidden_prompts = iter(["ReplacementPassword!42", "DifferentPassword!42"])

    def read_email(prompt: str) -> str:
        assert prompt == "Vendor email: "
        return next(prompts)

    def read_password(prompt: str) -> str:
        assert prompt in {
            "New password (12-128 characters): ",
            "Confirm new password: ",
        }
        return next(hidden_prompts)

    monkeypatch.setattr("builtins.input", read_email)
    monkeypatch.setattr(reset_password.getpass, "getpass", read_password)

    def unexpected_connection() -> None:
        pytest.fail("Database connection should not be attempted.")

    monkeypatch.setattr(reset_password, "create_mongo_client", unexpected_connection)

    assert reset_password.main() == 2
    assert capsys.readouterr().out.strip() == "Passwords do not match."


@pytest.mark.parametrize("password", ["Short123!", "p" * 129])
def test_password_reset_enforces_password_length_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    password: str,
) -> None:
    prompts = iter(["test@gmail.com"])
    hidden_prompts = iter([password, password])

    def read_email(prompt: str) -> str:
        assert prompt == "Vendor email: "
        return next(prompts)

    def read_password(prompt: str) -> str:
        assert prompt in {
            "New password (12-128 characters): ",
            "Confirm new password: ",
        }
        return next(hidden_prompts)

    def unexpected_connection() -> None:
        pytest.fail("Database connection should not be attempted.")

    monkeypatch.setattr("builtins.input", read_email)
    monkeypatch.setattr(reset_password.getpass, "getpass", read_password)
    monkeypatch.setattr(reset_password, "create_mongo_client", unexpected_connection)

    assert reset_password.main() == 2
    assert capsys.readouterr().out.strip() == (
        "Passwords must be between 12 and 128 characters."
    )
