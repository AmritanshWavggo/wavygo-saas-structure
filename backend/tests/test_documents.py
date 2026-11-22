import asyncio
import io
from fastapi.testclient import TestClient
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status

from app.main import app
from app.modules.auth.security import get_current_vendor
from app.modules.documents import service as documents_service_module
from app.modules.documents.service import DocumentService

client = TestClient(app)
TENANT_ID = "document-owner"


class FakeDocumentCollection:
    def __init__(self, record):
        self.record = dict(record)
        self.fail_update = False
        self.events = []

    @staticmethod
    def matches(document, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(FakeDocumentCollection.matches(document, item) for item in expected):
                    return False
            elif key == "$or":
                if not any(FakeDocumentCollection.matches(document, item) for item in expected):
                    return False
            elif document.get(key) != expected:
                return False
        return True

    def find_one(self, query):
        return dict(self.record) if self.matches(self.record, query) else None

    def update_one(self, query, update):
        if self.fail_update:
            raise RuntimeError("database update failed")
        if not self.matches(self.record, query):
            return type("UpdateResult", (), {"matched_count": 0})()
        self.events.append("database-update")
        self.record.update(update["$set"])
        return type("UpdateResult", (), {"matched_count": 1})()


class FakeDocumentDatabase:
    def __init__(self, documents):
        self.documents = documents

    def __getitem__(self, name):
        assert name == "documents"
        return self.documents


def document_record():
    return {
        "id": "DC-REPLACE-1",
        "name": "Vehicle insurance",
        "category": "Insurance",
        "scope": "Vehicle",
        "vehicle_id": "VH-1",
        "vehicle_name": "Test vehicle",
        "file_url": "https://cdn.test/old.pdf",
        "public_id": "old-document",
        "resource_type": "raw",
        "file_name": "old.pdf",
        "file_size": 5,
        "format": "pdf",
        "status": "Verified",
        "date": "Nov 01, 2026",
        "created_at": "2026-11-01T00:00:00+00:00",
        "updated_at": "2026-11-01T00:00:00+00:00",
        "tenant_id": TENANT_ID,
    }


def make_upload(filename="replacement.pdf", content_type="application/pdf", content=b"%PDF-new"):
    from starlette.datastructures import Headers
    from fastapi import UploadFile

    return UploadFile(
        file=io.BytesIO(content),
        size=len(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_list_documents():
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check that seeded items are returned
    doc = data[0]
    assert "id" in doc
    assert "file_url" in doc
    assert "name" in doc


def test_get_document():
    # Fetch list first
    list_res = client.get("/api/v1/documents")
    doc_id = list_res.json()[0]["id"]

    res = client.get(f"/api/v1/documents/{doc_id}")
    assert res.status_code == 200
    assert res.json()["id"] == doc_id


def test_update_document():
    list_res = client.get("/api/v1/documents")
    doc_id = list_res.json()[0]["id"]

    res = client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"status": "Verified", "notes": "Updated by test"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "Verified"
    assert data["notes"] == "Updated by test"


def test_upload_document_mocked():
    fake_file_content = b"%PDF-1.4 test dummy pdf content"
    files = {"file": ("test_permit.pdf", io.BytesIO(fake_file_content), "application/pdf")}
    data = {
        "name": "State Transport Permit",
        "category": "Permit",
        "scope": "Vehicle",
        "vehicle_id": "VH-1042",
        "vehicle_name": "Honda Activa 6G",
        "status_val": "In review",
        "notes": "Testing file upload",
    }

    mock_cloudinary_return = {
        "secure_url": "https://res.cloudinary.com/himuiwgh/image/upload/v1234/wavygo_documents/test_permit.pdf",
        "public_id": "wavygo_documents/test_permit",
        "format": "pdf",
        "bytes": len(fake_file_content),
    }

    with patch("cloudinary.uploader.upload", return_value=mock_cloudinary_return):
        res = client.post("/api/v1/documents/upload", files=files, data=data)
        assert res.status_code == 201
        res_data = res.json()
        assert res_data["name"] == "State Transport Permit"
        assert res_data["category"] == "Permit"
        assert res_data["file_url"] == mock_cloudinary_return["secure_url"]
        assert res_data["public_id"] == mock_cloudinary_return["public_id"]
        assert res_data["id"].startswith("DC-")


def replacement_service(monkeypatch, *, fail_update=False):
    collection = FakeDocumentCollection(document_record())
    collection.fail_update = fail_update
    service = DocumentService()
    monkeypatch.setattr(service, "_get_db", lambda: FakeDocumentDatabase(collection))
    return service, collection


def test_replace_document_updates_existing_record_and_deletes_old_asset_after_save(monkeypatch):
    service, collection = replacement_service(monkeypatch)
    operations = []

    def upload(*args, **kwargs):
        operations.append("cloudinary-upload")
        return {
            "secure_url": "https://cdn.test/new.pdf",
            "public_id": "new-document",
            "resource_type": "raw",
            "format": "pdf",
            "bytes": 8,
        }

    def destroy(public_id, **kwargs):
        operations.append(f"cloudinary-delete:{public_id}")
        return {"result": "ok"}

    monkeypatch.setattr(documents_service_module.cloudinary.uploader, "upload", upload)
    monkeypatch.setattr(documents_service_module.cloudinary.uploader, "destroy", destroy)
    result = asyncio.run(
        service.replace_document("DC-REPLACE-1", make_upload(), TENANT_ID)
    )

    assert result is not None
    assert result.id == "DC-REPLACE-1"
    assert result.vehicle_id == "VH-1"
    assert result.file_url == "https://cdn.test/new.pdf"
    assert result.file_name == "replacement.pdf"
    assert result.resource_type == "raw"
    assert collection.record["id"] == "DC-REPLACE-1"
    assert collection.record["vehicle_id"] == "VH-1"
    assert len([collection.record]) == 1
    assert operations.index("cloudinary-upload") < operations.index("cloudinary-delete:old-document")
    assert collection.events == ["database-update"]


def test_replace_document_upload_failure_preserves_existing_record(monkeypatch):
    service, collection = replacement_service(monkeypatch)
    before = dict(collection.record)
    destroy = patch("app.modules.documents.service.cloudinary.uploader.destroy")

    def fail_upload(*args, **kwargs):
        raise RuntimeError("Cloudinary is unavailable")

    monkeypatch.setattr(documents_service_module.cloudinary.uploader, "upload", fail_upload)
    with destroy as delete_asset:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.replace_document("DC-REPLACE-1", make_upload(), TENANT_ID))

    assert error.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert collection.record == before
    delete_asset.assert_not_called()


def test_replace_document_database_failure_cleans_new_asset_and_preserves_old(monkeypatch):
    service, collection = replacement_service(monkeypatch, fail_update=True)
    before = dict(collection.record)
    deleted = []
    monkeypatch.setattr(
        documents_service_module.cloudinary.uploader,
        "upload",
        lambda *args, **kwargs: {
            "secure_url": "https://cdn.test/new.pdf",
            "public_id": "new-document",
            "resource_type": "raw",
            "format": "pdf",
        },
    )
    monkeypatch.setattr(
        documents_service_module.cloudinary.uploader,
        "destroy",
        lambda public_id, **kwargs: deleted.append((public_id, kwargs.get("resource_type"))),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.replace_document("DC-REPLACE-1", make_upload(), TENANT_ID))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert collection.record == before
    assert deleted == [("new-document", "raw")]


@pytest.mark.parametrize(
    "file",
    [
        make_upload("replacement.exe", "application/octet-stream"),
        make_upload("too-large.pdf", "application/pdf", b"x" * (10 * 1024 * 1024 + 1)),
        make_upload("empty.pdf", "application/pdf", b""),
    ],
    ids=["unsupported-type", "oversized-file", "empty-file"],
)
def test_replace_document_rejects_invalid_files_before_upload(monkeypatch, file):
    service, collection = replacement_service(monkeypatch)
    before = dict(collection.record)
    upload = patch("app.modules.documents.service.cloudinary.uploader.upload")
    with upload as upload_file:
        with pytest.raises(HTTPException):
            asyncio.run(service.replace_document("DC-REPLACE-1", file, TENANT_ID))

    assert collection.record == before
    upload_file.assert_not_called()


def test_replace_document_requires_authenticated_vendor():
    def reject_vendor():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    app.dependency_overrides[get_current_vendor] = reject_vendor
    try:
        response = client.put(
            "/api/v1/documents/DC-REPLACE-1/file",
            files={"file": ("replacement.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_replace_document_api_keeps_id_and_returns_updated_record(monkeypatch):
    collection = FakeDocumentCollection(document_record())
    database = FakeDocumentDatabase(collection)
    monkeypatch.setattr(documents_service_module.document_service, "_get_db", lambda: database)
    monkeypatch.setattr(
        documents_service_module.cloudinary.uploader,
        "upload",
        lambda *args, **kwargs: {
            "secure_url": "https://cdn.test/refreshed.pdf",
            "public_id": "refreshed-document",
            "resource_type": "raw",
            "format": "pdf",
            "bytes": 12,
        },
    )
    monkeypatch.setattr(
        documents_service_module.cloudinary.uploader,
        "destroy",
        lambda *args, **kwargs: {"result": "ok"},
    )
    app.dependency_overrides[get_current_vendor] = lambda: {"_id": TENANT_ID, "role": "owner"}
    try:
        response = client.put(
            "/api/v1/documents/DC-REPLACE-1/file",
            files={"file": ("refreshed.pdf", io.BytesIO(b"%PDF-refreshed"), "application/pdf")},
        )
        refreshed = client.get("/api/v1/documents/DC-REPLACE-1")
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == "DC-REPLACE-1"
    assert response.json()["vehicle_id"] == "VH-1"
    assert refreshed.status_code == 200
    assert refreshed.json()["file_url"] == "https://cdn.test/refreshed.pdf"
    assert len([collection.record]) == 1


def test_replace_document_requires_a_file_and_rejects_non_owner(monkeypatch):
    app.dependency_overrides[get_current_vendor] = lambda: {"_id": TENANT_ID, "role": "member"}
    try:
        unauthorized = client.put("/api/v1/documents/DC-REPLACE-1/file")
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)
    assert unauthorized.status_code == 422

    app.dependency_overrides[get_current_vendor] = lambda: {
        "_id": TENANT_ID,
        "role": "member",
    }
    try:
        forbidden = client.put(
            "/api/v1/documents/DC-REPLACE-1/file",
            files={"file": ("replacement.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)
    assert forbidden.status_code == 403
