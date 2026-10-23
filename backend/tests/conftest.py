from __future__ import annotations

from copy import deepcopy
import re

import pytest
from bson import ObjectId

from app.modules.vehicles import router as vehicles_router


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def skip(self, count: int) -> "FakeCursor":
        self.documents = self.documents[count:]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.fail_insert = False
        self.fail_update = False

    @staticmethod
    def _matches(document: dict, query: dict) -> bool:
        if "$or" in query:
            return any(FakeCollection._matches(document, item) for item in query["$or"])
        for key, expected in query.items():
            value = document.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and value == expected["$ne"]:
                    return False
                if "$in" in expected and value not in expected["$in"]:
                    return False
                if "$regex" in expected and not re.search(
                    expected["$regex"], str(value or ""), re.IGNORECASE if expected.get("$options") == "i" else 0
                ):
                    return False
            elif value != expected:
                return False
        return True

    def find_one(self, query: dict):
        for document in self.documents:
            if self._matches(document, query):
                return deepcopy(document)
        return None

    def insert_one(self, document: dict):
        if self.fail_insert:
            raise RuntimeError("database write failed")
        stored = deepcopy(document)
        stored["_id"] = ObjectId()
        self.documents.append(stored)
        return type("InsertResult", (), {"inserted_id": stored["_id"]})()

    def update_one(self, query: dict, update: dict):
        if self.fail_update:
            raise RuntimeError("database write failed")
        for document in self.documents:
            if self._matches(document, query):
                document.update(deepcopy(update.get("$set", {})))
                return

    def delete_one(self, query: dict):
        self.documents = [d for d in self.documents if not self._matches(d, query)]

    def count_documents(self, query: dict) -> int:
        return sum(self._matches(document, query) for document in self.documents)

    def find(self, query: dict) -> FakeCursor:
        return FakeCursor([d for d in self.documents if self._matches(d, query)])


@pytest.fixture
def vehicle_store(monkeypatch):
    vehicles = FakeCollection()
    bookings = FakeCollection()
    uploads: list[tuple[bytes, str, str]] = []
    deletes: list[tuple[str, str]] = []

    def upload(file_bytes: bytes, folder: str, resource_type: str) -> dict:
        uploads.append((file_bytes, folder, resource_type))
        return {"url": f"https://cdn.test/{len(uploads)}", "public_id": f"asset-{len(uploads)}"}

    def delete(public_id: str, resource_type: str = "image") -> dict:
        deletes.append((public_id, resource_type))
        return {"result": "ok"}

    monkeypatch.setattr(vehicles_router, "_get_vehicles_col", lambda: vehicles)
    monkeypatch.setattr(vehicles_router, "_get_bookings_col", lambda: bookings)
    monkeypatch.setattr(vehicles_router.cloudinary_service, "upload_file", upload)
    monkeypatch.setattr(vehicles_router.cloudinary_service, "delete_file", delete)
    return type("VehicleStore", (), {
        "vehicles": vehicles,
        "bookings": bookings,
        "uploads": uploads,
        "deletes": deletes,
    })()
