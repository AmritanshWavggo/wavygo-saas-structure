import io
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


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
