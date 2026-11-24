from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.modules.auth.security import get_current_vendor
from app.db.mongodb import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staff", tags=["staff"])

StaffStatus = Literal["Active", "Inactive"]
StaffRole = Literal[
    "Fleet manager",
    "Operations associate",
    "Customer support",
    "Delivery associate",
    "Administrator",
]


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    role: StaffRole
    phone: str = Field(min_length=7, max_length=25)
    salary: float = Field(ge=0)
    attendance: str = Field(default="Not recorded", max_length=100)
    nextSalary: str = Field(default="", max_length=50)
    status: StaffStatus = "Active"


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: StaffRole | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=25)
    salary: float | None = Field(default=None, ge=0)
    attendance: str | None = Field(default=None, max_length=100)
    nextSalary: str | None = Field(default=None, max_length=50)
    status: StaffStatus | None = None


class StaffStatusUpdate(BaseModel):
    status: StaffStatus


def get_staff_collection(request: Request) -> Collection:
    database = getattr(request.app.state, "database", None)

    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not configured.",
        )

    return database["staff_members"]


def serialize_staff(document: dict[str, Any] | None) -> dict[str, Any]:
    if not document:
        return {}
    result = dict(document)
    result["id"] = str(result.pop("_id"))
    result.pop("tenant_id", None)
    return result


def parse_staff_id(staff_id: str) -> ObjectId:
    if not ObjectId.is_valid(staff_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid staff ID.",
        )
    return ObjectId(staff_id)


def storage_error() -> NoReturn:
    logger.exception("Staff database operation failed.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Staff storage is unavailable.",
    )


@router.get("", summary="List staff members")
@router.get("/", summary="List staff members (trailing slash)")
def list_staff(
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    try:
        query = {"tenant_id": vendor["_id"]}
        documents = list(
            collection.find(query).sort("created_at", -1)
        )
        items = [serialize_staff(doc) for doc in documents]
        return {"items": items, "total": len(items)}
    except PyMongoError:
        storage_error()


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create staff member")
@router.post("/", status_code=status.HTTP_201_CREATED, summary="Create staff member (trailing slash)")
def create_staff(
    staff: StaffCreate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        **staff.model_dump(),
        "tenant_id": vendor["_id"],
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = collection.insert_one(document)
        document["_id"] = result.inserted_id
        return serialize_staff(document)
    except PyMongoError:
        storage_error()


@router.patch("/{staff_id}/status", summary="Update staff member status")
def update_staff_status(
    staff_id: str,
    changes: StaffStatusUpdate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}

    try:
        result = collection.update_one(
            query,
            {
                "$set": {
                    "status": changes.status,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Staff member not found.")

        document = collection.find_one(query)
        if not document:
            raise HTTPException(status_code=404, detail="Staff member not found.")
        return serialize_staff(document)
    except PyMongoError:
        storage_error()


@router.put("/{staff_id}", summary="Update staff member details")
def update_staff(
    staff_id: str,
    changes: StaffUpdate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    update = changes.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=400, detail="No changes provided.")

    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    update["updated_at"] = datetime.now(timezone.utc)

    try:
        result = collection.update_one(query, {"$set": update})
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Staff member not found.")

        document = collection.find_one(query)
        if not document:
            raise HTTPException(status_code=404, detail="Staff member not found.")
        return serialize_staff(document)
    except PyMongoError:
        storage_error()


DOCUMENTS_UPLOAD_DIR = Path("backend/uploads/staff_documents")
MAX_STAFF_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
STAFF_DOCUMENT_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


@router.post("/{staff_id}/documents", status_code=status.HTTP_201_CREATED, summary="Upload staff document")
async def upload_staff_document(
    staff_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
    file: UploadFile = File(...),
    category: str = Form("ID Proof"),
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG, and PNG files are supported.",
        )

    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    staff_folder = DOCUMENTS_UPLOAD_DIR / staff_id
    staff_folder.mkdir(parents=True, exist_ok=True)

    file_dest = staff_folder / f"{doc_id}_{file.filename}"
    content = await file.read()
    file_dest.write_bytes(content)

    doc_entry = {
        "id": doc_id,
        "name": file.filename,
        "category": category,
        "url": f"/api/v1/staff/{staff_id}/documents/{doc_id}/download",
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "file_path": str(file_dest),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    collection.update_one(query, {"$push": {"documents": doc_entry}})
    return doc_entry


@router.put(
    "/{staff_id}/documents/{document_id}",
    summary="Replace staff document",
)
async def replace_staff_document(
    staff_id: str,
    document_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    documents = staff_member.get("documents", [])
    existing = next((item for item in documents if item.get("id") == document_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found.")

    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    extension = Path(filename).suffix.lower()
    if not filename or STAFF_DOCUMENT_MIME_TYPES.get(extension) != file.content_type:
        raise HTTPException(
            status_code=422,
            detail="Only PDF, JPG, JPEG, and PNG files are supported.",
        )
    if file.size is not None and file.size > MAX_STAFF_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit.")

    content = await file.read(MAX_STAFF_DOCUMENT_SIZE_BYTES + 1)
    if len(content) > MAX_STAFF_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit.")
    if not content:
        raise HTTPException(status_code=422, detail="The replacement document cannot be empty.")

    new_path = DOCUMENTS_UPLOAD_DIR / staff_id / f"{document_id}_{uuid.uuid4().hex}_{filename}"
    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(content)
    except OSError as exc:
        logger.exception("Could not save replacement staff document.")
        raise HTTPException(
            status_code=500,
            detail="Could not store the replacement document.",
        ) from exc

    updated = {
        **existing,
        "name": filename,
        "url": f"/api/v1/staff/{staff_id}/documents/{document_id}/download",
        "content_type": file.content_type,
        "size": len(content),
        "file_path": str(new_path),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        result = collection.update_one(
            {**query, "documents.id": document_id},
            {"$set": {"documents.$": updated}},
        )
        if result.matched_count != 1:
            new_path.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Document not found.")
    except HTTPException:
        raise
    except Exception as exc:
        new_path.unlink(missing_ok=True)
        logger.exception("Could not update staff document metadata.")
        raise HTTPException(
            status_code=503,
            detail="Could not save the replacement. The existing document was preserved.",
        ) from exc

    old_path = existing.get("file_path")
    if old_path and old_path != str(new_path) and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            logger.exception("Could not remove replaced staff document file %s.", old_path)

    return updated


@router.get("/{staff_id}/documents", summary="List staff documents")
def list_staff_documents(
    staff_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    docs = staff_member.get("documents", [])
    return {"items": docs, "total": len(docs)}


@router.get("/{staff_id}/documents/{document_id}/download", summary="Download staff document")
def download_staff_document(
    staff_id: str,
    document_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> FileResponse:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    docs = staff_member.get("documents", [])
    matching = next((d for d in docs if d.get("id") == document_id), None)
    if not matching or not matching.get("file_path") or not os.path.exists(matching["file_path"]):
        raise HTTPException(status_code=404, detail="Document file not found.")

    return FileResponse(
        matching["file_path"],
        filename=matching.get("name", "document"),
        media_type=matching.get("content_type", "application/octet-stream"),
    )


@router.delete("/{staff_id}/documents/{document_id}", summary="Delete staff document")
def delete_staff_document(
    staff_id: str,
    document_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    docs = staff_member.get("documents", [])
    matching = next((d for d in docs if d.get("id") == document_id), None)
    if matching and matching.get("file_path") and os.path.exists(matching["file_path"]):
        try:
            os.remove(matching["file_path"])
        except Exception:
            pass

    collection.update_one(query, {"$pull": {"documents": {"id": document_id}}})
    return {"detail": "Document deleted successfully.", "id": document_id}


@router.delete("/{staff_id}", summary="Delete staff member")
def delete_staff(
    staff_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection, Depends(get_staff_collection)],
) -> dict[str, Any]:
    object_id = parse_staff_id(staff_id)
    query = {"_id": object_id, "tenant_id": vendor["_id"]}
    staff_member = collection.find_one(query)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    staff_folder = DOCUMENTS_UPLOAD_DIR / staff_id
    if staff_folder.exists():
        import shutil
        shutil.rmtree(staff_folder, ignore_errors=True)

    if hasattr(collection, "delete_one"):
        collection.delete_one(query)
    return {"detail": "Staff member deleted successfully.", "id": staff_id}
