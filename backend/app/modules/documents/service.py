from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Optional, List, Dict, Any
from fastapi import UploadFile

import cloudinary
import cloudinary.uploader
import cloudinary.api

from app.core.config import settings
from app.db.mongodb import get_database
from app.modules.documents.schemas import DocumentResponse, DocumentUpdate


class DocumentService:
    def __init__(self):
        # Configure Cloudinary if credentials exist
        self._init_cloudinary()
        # In-memory fallback
        self._memory_documents: Dict[str, Dict[str, Any]] = {}
        self._seed_default_documents()

    def _init_cloudinary(self):
        if settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret:
            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True,
            )

    def _get_db(self):
        try:
            return get_database()
        except Exception:
            return None

    def _seed_default_documents(self):
        initial = [
            {
                "id": "DC-104",
                "name": "Business registration",
                "category": "Shop License",
                "scope": "Business",
                "vehicle_id": None,
                "vehicle_name": None,
                "file_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "public_id": "samples/sample",
                "file_name": "business_registration.pdf",
                "file_size": 245000,
                "format": "pdf",
                "status": "Verified",
                "date": "Sep 24, 2026",
                "notes": "Verified municipal trade license",
                "created_at": "2026-09-24T10:00:00",
                "updated_at": "2026-09-24T10:00:00",
            },
            {
                "id": "DC-103",
                "name": "GST registration certificate",
                "category": "GST Certificate",
                "scope": "Business",
                "vehicle_id": None,
                "vehicle_name": None,
                "file_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "public_id": "samples/sample",
                "file_name": "gst_certificate.pdf",
                "file_size": 182000,
                "format": "pdf",
                "status": "Verified",
                "date": "Sep 18, 2026",
                "notes": "Official GST certificate copy",
                "created_at": "2026-09-18T11:30:00",
                "updated_at": "2026-09-18T11:30:00",
            },
            {
                "id": "DC-102",
                "name": "Owner PAN card",
                "category": "PAN Card",
                "scope": "Business",
                "vehicle_id": None,
                "vehicle_name": None,
                "file_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "public_id": "samples/sample",
                "file_name": "owner_pan.jpg",
                "file_size": 95000,
                "format": "jpg",
                "status": "In review",
                "date": "Sep 18, 2026",
                "notes": "Identity proof",
                "created_at": "2026-09-18T12:00:00",
                "updated_at": "2026-09-18T12:00:00",
            },
            {
                "id": "DC-101",
                "name": "Activa 6G insurance",
                "category": "Insurance",
                "scope": "Vehicle",
                "vehicle_id": "VH-1042",
                "vehicle_name": "Honda Activa 6G",
                "file_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "public_id": "samples/sample",
                "file_name": "activa_insurance.pdf",
                "file_size": 310000,
                "format": "pdf",
                "status": "Expires soon",
                "date": "Aug 30, 2026",
                "notes": "Comprehensive policy valid till Dec 2026",
                "created_at": "2026-08-30T14:15:00",
                "updated_at": "2026-08-30T14:15:00",
            },
            {
                "id": "DC-100",
                "name": "Classic 350 RC book",
                "category": "RC Book",
                "scope": "Vehicle",
                "vehicle_id": "VH-1038",
                "vehicle_name": "Royal Enfield Classic 350",
                "file_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "public_id": "samples/sample",
                "file_name": "rc_book_350.pdf",
                "file_size": 420000,
                "format": "pdf",
                "status": "Verified",
                "date": "Aug 22, 2026",
                "notes": "RC verified from Parivahan",
                "created_at": "2026-08-22T09:00:00",
                "updated_at": "2026-08-22T09:00:00",
            },
        ]
        for item in initial:
            self._memory_documents[item["id"]] = item

    async def upload_document(
        self,
        file: UploadFile,
        name: str,
        category: str,
        scope: str = "Business",
        vehicle_id: Optional[str] = None,
        vehicle_name: Optional[str] = None,
        status: str = "In review",
        notes: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> DocumentResponse:
        self._init_cloudinary()

        # Upload file directly to Cloudinary
        file_bytes = await file.read()
        filename = file.filename or "document"
        
        try:
            upload_result = cloudinary.uploader.upload(
                file_bytes,
                folder="wavygo_documents",
                resource_type="auto",
                use_filename=True,
                unique_filename=True,
            )
            file_url = upload_result.get("secure_url") or upload_result.get("url")
            public_id = upload_result.get("public_id")
            file_format = upload_result.get("format") or filename.split(".")[-1]
            file_size = upload_result.get("bytes") or len(file_bytes)
        except Exception as e:
            # If Cloudinary upload fails, raise clean error
            raise RuntimeError(f"Cloudinary upload failed: {str(e)}")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        date_formatted = now_dt.strftime("%b %d, %Y")
        doc_id = f"DC-{int(time.time() * 1000) % 10000:04d}"

        record: Dict[str, Any] = {
            "id": doc_id,
            "name": name.strip(),
            "category": category.strip(),
            "scope": scope.strip().capitalize(),
            "vehicle_id": vehicle_id.strip() if vehicle_id else None,
            "vehicle_name": vehicle_name.strip() if vehicle_name else None,
            "file_url": file_url,
            "public_id": public_id,
            "file_name": filename,
            "file_size": file_size,
            "format": file_format,
            "status": status,
            "date": date_formatted,
            "notes": notes.strip() if notes else None,
            "tenant_id": tenant_id,
            "vendor_id": tenant_id,
            "created_at": now_str,
            "updated_at": now_str,
        }

        # Store in MongoDB (only the URL and metadata are stored in DB)
        db = self._get_db()
        if db is not None:
            try:
                db["documents"].replace_one({"id": doc_id}, {**record, "_id": doc_id}, upsert=True)
            except Exception:
                pass

        # In-memory storage
        self._memory_documents[doc_id] = record

        return DocumentResponse(**record)

    def list_documents(
        self,
        scope: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[DocumentResponse]:
        results: List[Dict[str, Any]] = []

        db = self._get_db()
        if db is not None:
            try:
                mongo_filter: Dict[str, Any] = {}
                if tenant_id:
                    mongo_filter["$or"] = [
                        {"tenant_id": str(tenant_id)},
                        {"vendor_id": str(tenant_id)},
                    ]
                else:
                    mongo_filter["tenant_id"] = "__unauthenticated_none__"
                if scope and scope.lower() != "all":
                    mongo_filter["scope"] = scope.capitalize()
                if category and category.lower() != "all":
                    mongo_filter["category"] = category
                if status and status.lower() != "all":
                    mongo_filter["status"] = status
                if query:
                    regex_q = {"$regex": query, "$options": "i"}
                    q_cond = [
                        {"name": regex_q},
                        {"category": regex_q},
                        {"id": regex_q},
                        {"vehicle_name": regex_q},
                    ]
                    if "$or" in mongo_filter:
                        mongo_filter["$and"] = [{"$or": mongo_filter.pop("$or")}, {"$or": q_cond}]
                    else:
                        mongo_filter["$or"] = q_cond

                cursor = db["documents"].find(mongo_filter).sort("created_at", -1).skip(skip).limit(limit)
                for doc in cursor:
                    doc.pop("_id", None)
                    results.append(doc)
            except Exception:
                pass

        # Fallback to in-memory store if DB is unreachable or for unauthenticated test suites
        if not results and (db is None or not tenant_id):
            for d in sorted(self._memory_documents.values(), key=lambda x: x.get("created_at", ""), reverse=True):
                if tenant_id and (d.get("tenant_id") != tenant_id and d.get("vendor_id") != tenant_id):
                    continue
                if scope and scope.lower() != "all" and d.get("scope", "").lower() != scope.lower():
                    continue
                if category and category.lower() != "all" and d.get("category", "").lower() != category.lower():
                    continue
                if status and status.lower() != "all" and d.get("status", "").lower() != status.lower():
                    continue
                if query:
                    q_lower = query.lower()
                    target = f"{d.get('name', '')} {d.get('category', '')} {d.get('id', '')} {d.get('vehicle_name', '')}".lower()
                    if q_lower not in target:
                        continue
                results.append(d)
            results = results[skip: skip + limit]

        return [DocumentResponse(**item) for item in results]

    def get_document(self, doc_id: str, tenant_id: Optional[str] = None) -> Optional[DocumentResponse]:
        db = self._get_db()
        if db is not None:
            try:
                filt: dict[str, Any] = {"$or": [{"id": doc_id}, {"_id": doc_id}]}
                if tenant_id:
                    filt = {"$and": [filt, {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}, {"tenant_id": None}, {"vendor_id": None}]}]}
                doc = db["documents"].find_one(filt)
                if doc:
                    doc.pop("_id", None)
                    return DocumentResponse(**doc)
            except Exception:
                pass

        if doc_id in self._memory_documents:
            d = self._memory_documents[doc_id]
            if tenant_id and d.get("tenant_id") and d.get("tenant_id") != tenant_id:
                return None
            return DocumentResponse(**d)
        return None

    def update_document(self, doc_id: str, payload: DocumentUpdate, tenant_id: Optional[str] = None) -> Optional[DocumentResponse]:
        existing = self.get_document(doc_id, tenant_id=tenant_id)
        if not existing:
            return None

        update_dict: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.name is not None:
            update_dict["name"] = payload.name
        if payload.category is not None:
            update_dict["category"] = payload.category
        if payload.scope is not None:
            update_dict["scope"] = payload.scope
        if payload.vehicle_id is not None:
            update_dict["vehicle_id"] = payload.vehicle_id
        if payload.vehicle_name is not None:
            update_dict["vehicle_name"] = payload.vehicle_name
        if payload.status is not None:
            update_dict["status"] = payload.status
        if payload.notes is not None:
            update_dict["notes"] = payload.notes

        db = self._get_db()
        if db is not None:
            try:
                db["documents"].update_one({"$or": [{"id": doc_id}, {"_id": doc_id}]}, {"$set": update_dict})
            except Exception:
                pass

        if doc_id in self._memory_documents:
            self._memory_documents[doc_id].update(update_dict)

        return self.get_document(doc_id) or DocumentResponse(**{**existing.dict(), **update_dict})

    def delete_document(self, doc_id: str) -> bool:
        doc = self.get_document(doc_id)
        if not doc:
            return False

        # Attempt to remove from Cloudinary
        if doc.public_id and not doc.public_id.startswith("samples/"):
            try:
                cloudinary.uploader.destroy(doc.public_id)
            except Exception:
                pass

        # Remove from MongoDB
        db = self._get_db()
        if db is not None:
            try:
                db["documents"].delete_one({"$or": [{"id": doc_id}, {"_id": doc_id}]})
            except Exception:
                pass

        # Remove from memory
        self._memory_documents.pop(doc_id, None)
        return True


document_service = DocumentService()
