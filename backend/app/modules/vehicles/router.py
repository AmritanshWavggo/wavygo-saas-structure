"""
Vehicles router — Phase 2.

All endpoints live under the prefix /api/v1/vehicles (mounted in api/v1/router.py).

Route order matters: fixed paths (/list, /{id}/show-on-wavygo) are declared
BEFORE the plain /{id} catch-all so FastAPI does not swallow them.

Auth:
    Every route depends on get_current_tenant.  Replace the stub body in
    app/modules/auth/deps.py with real JWT / API-key validation.

Cloudinary calls are blocking (the cloudinary SDK is synchronous).
All route handlers that call Cloudinary are plain ``def`` (not async def)
so they run in FastAPI's thread-pool and do not block the event loop.

Data rules enforced here:
    1. price == dailyRate — written together on create and update.
    2. status mirrors showOnWavygo — set together on create, update, toggle.
    3. availability (alias fleetAvailability) is the only fleet field; toggle
       does NOT touch it.
    4. Documents deleted with the resource_type stored alongside them.
    5. Legacy / malformed records returned as raw dicts (id coerced to str).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Optional, Union

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.db.mongodb import get_database
from app.modules.auth.deps import TenantContext, get_current_tenant
from app.modules.vehicles.models import (
    DocumentType,
    FleetAvailability,
    ListingStatus,
    VehicleFile,
    VehicleModel,
    VehiclePhoto,
    VehicleType,
)
from app.modules.vehicles.schemas import (
    ShowOnWavygoSchema,
    VehicleCreateSchema,
    VehicleUpdateSchema,
)
from app.modules.vehicles.upload_middleware import (
    ALLOWED_DOCUMENT_MIME_TYPES,
    ALLOWED_PHOTO_MIME_TYPES,
    MAX_DOCUMENT_SIZE_BYTES,
    MAX_PHOTO_SIZE_BYTES,
)
from app.services import cloudinary_service
from app.services.rc_service import check_rc_duplicate, normalise_rc, validate_rc_format

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VEHICLES_COLLECTION = "vehicles"
_BOOKINGS_COLLECTION = "bookings"
_CLOUDINARY_PHOTO_FOLDER = "wavygo/vehicles/photos"
_CLOUDINARY_DOCUMENT_FOLDER = "wavygo/vehicles/documents"
_LIST_MAX_LIMIT = 100
_LIST_DEFAULT_LIMIT = 20


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_vehicles_col(db=None):
    """Return the vehicles PyMongo collection.  Raises 503 if DB unavailable."""
    if db is None:
        db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available.",
        )
    return db[_VEHICLES_COLLECTION]


def _get_bookings_col(db=None):
    """Return the bookings PyMongo collection.  Raises 503 if DB unavailable."""
    if db is None:
        db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available.",
        )
    return db[_BOOKINGS_COLLECTION]


# FIX: Access maintenance collection to verify open jobs before vehicle state mutations
def _get_maintenance_col(db=None):
    """Return the maintenance collection.  Raises 503 if DB is unavailable."""
    if db is None:
        db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available.",
        )
    return db["maintenance"]


def _parse_object_id(vehicle_id: str) -> Any:
    """Parse a string into ObjectId if valid, else return the vehicle_id string."""
    try:
        if ObjectId.is_valid(vehicle_id):
            return ObjectId(vehicle_id)
    except Exception:
        pass
    return vehicle_id


def _extract_tenant_id(tenant: Any) -> Optional[str]:
    if not tenant:
        return None
    if isinstance(tenant, dict):
        return (
            tenant.get("tenant_id")
            or tenant.get("tenantId")
            or tenant.get("vendor_id")
            or (str(tenant["_id"]) if "_id" in tenant else None)
        )
    return (
        getattr(tenant, "tenant_id", None)
        or getattr(tenant, "tenantId", None)
        or getattr(tenant, "vendor_id", None)
        or getattr(tenant, "id", None)
    )


def _vehicle_query(vehicle_id: str, tenant: Any = None) -> dict[str, Any]:
    conds: list[dict[str, Any]] = [{"id": vehicle_id}, {"_id": vehicle_id}]
    try:
        if ObjectId.is_valid(vehicle_id):
            conds.append({"_id": ObjectId(vehicle_id)})
    except Exception:
        pass
    base_query: dict[str, Any] = {"$or": conds}
    tid = _extract_tenant_id(tenant)
    if tid:
        return {
            "$and": [
                base_query,
                {"$or": [{"tenant_id": str(tid)}, {"tenantId": str(tid)}]},
            ]
        }
    return base_query


# FIX: Guard against manual Available/Rented state changes that would bypass an open maintenance or rental workflow
def _operational_state_change_is_blocked(existing: dict[str, Any], tenant: Any) -> bool:
    """Whether a manual Available/Rented state change would bypass an open workflow."""
    tenant_id = _extract_tenant_id(tenant)
    vehicle_id = str(existing.get("id") or existing.get("_id"))
    vehicle_name = existing.get("name") or existing.get("makeModel")
    tenant_filter = {"$or": [{"tenant_id": tenant_id}, {"tenantId": tenant_id}, {"vendor_id": tenant_id}]}
    vehicle_filter = {"$or": [{"vehicle_id": vehicle_id}, {"vehicle": vehicle_name}]}
    open_maintenance = _get_maintenance_col().find_one(
        {"$and": [tenant_filter, vehicle_filter, {"status": {"$nin": ["Completed", "Cancelled"]}}]}
    )
    active_booking = _get_bookings_col().find_one(
        {
            "$and": [
                tenant_filter,
                {"status": {"$in": ["Active", "Returned"]}},
                {"$or": [{"vehicle_details.id": vehicle_id}, {"vehicle": vehicle_name}, {"vehicleId": vehicle_id}]},
            ]
        }
    )
    return bool(open_maintenance or active_booking)


def _doc_to_response(doc: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    Convert a raw MongoDB document to a JSON-safe response dict.

    - Preserves custom id (e.g. VH-2001) if present; otherwise converts _id (ObjectId) to string.
    - Does NOT re-validate via Pydantic so legacy records with unexpected
      enum values or missing fields are returned as-is (rule 5).
    """
    if not doc:
        return {}
    res = dict(doc)
    custom_id = res.get("id")
    raw_id = res.pop("_id", None)
    res["id"] = custom_id or (str(raw_id) if raw_id is not None else None)
    return res


def _validate_file_inline(
    file: UploadFile,
    allowed_types: frozenset,
    max_bytes: int,
    label: str,
) -> None:
    """Validate a single UploadFile; raise HTTP 422 on violations."""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid {label} type '{file.content_type}'. "
                f"Allowed: {sorted(allowed_types)}."
            ),
        )
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{label.capitalize()} exceeds the "
                f"{max_bytes // (1024 * 1024)} MB limit."
            ),
        )


def _cloudinary_resource_type(content_type: str) -> str:
    """Map a MIME type to the Cloudinary resource_type parameter."""
    return "raw" if content_type == "application/pdf" else "auto"


def _delete_cloudinary_files(files: list[dict]) -> None:
    """
    Delete a list of Cloudinary file metadata dicts.

    Each dict must have keys ``publicId`` and optionally ``resourceType``
    (defaults to "image").  Errors are logged but not re-raised — used in
    cleanup paths where we don't want to mask the original error.
    """
    for f in files:
        pid = f.get("publicId") or f.get("public_id")
        rtype = f.get("resourceType") or f.get("resource_type", "image")
        if not pid:
            continue
        try:
            cloudinary_service.delete_file(pid, resource_type=rtype)
        except Exception as exc:
            logger.error(
                "Failed to delete Cloudinary asset public_id=%s resource_type=%s: %s",
                pid,
                rtype,
                exc,
            )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 6. List vehicles  (fixed path — declared before /{id})
# ---------------------------------------------------------------------------


@router.get("", summary="List vehicles")
@router.get("/", include_in_schema=False)
def list_vehicles(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    # Search
    search: Optional[str] = Query(default=None, max_length=100),
    # Filters
    type: Optional[str] = Query(default=None),
    fuel: Optional[str] = Query(default=None),
    fleet_availability: Optional[str] = Query(default=None, alias="fleetAvailability"),
    # Listing param: all | online | offline
    listing: str = Query(default="all", pattern="^(all|online|offline)$"),
    # Pagination
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=_LIST_DEFAULT_LIMIT, ge=1, le=_LIST_MAX_LIMIT),
) -> dict:
    """
    List vehicles with optional search, filters, and pagination.

    ``listing`` values:
    - ``all``     — no filter on showOnWavygo (default)
    - ``online``  — showOnWavygo is True
    - ``offline`` — showOnWavygo is False or missing
    """
    col = _get_vehicles_col()
    query: dict[str, Any] = {}

    # Search — escape user input before building a regex (never pass raw input)
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"name": {"$regex": escaped, "$options": "i"}},
            {"registration": {"$regex": escaped, "$options": "i"}},
            {"registrationNumber": {"$regex": escaped, "$options": "i"}},
            {"color": {"$regex": escaped, "$options": "i"}},
        ]

    # Enum filters — validate against known values; 422 on bad input
    if type is not None:
        allowed_types = {e.value for e in VehicleType}
        if type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid type '{type}'. Allowed: {sorted(allowed_types)}.",
            )
        query["type"] = type

    if fuel is not None:
        from app.modules.vehicles.models import FuelType
        allowed_fuels = {e.value for e in FuelType}
        if fuel not in allowed_fuels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid fuel '{fuel}'. Allowed: {sorted(allowed_fuels)}.",
            )
        query["fuel"] = fuel

    if fleet_availability is not None:
        allowed_fa = {e.value for e in FleetAvailability}
        if fleet_availability not in allowed_fa:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Invalid fleetAvailability '{fleet_availability}'. "
                    f"Allowed: {sorted(allowed_fa)}."
                ),
            )
        query["fleetAvailability"] = fleet_availability

    # Listing filter
    if listing == "online":
        query["showOnWavygo"] = True
    elif listing == "offline":
        query["showOnWavygo"] = {"$ne": True}

    tid = _extract_tenant_id(tenant)
    if tid:
        tenant_filter = {"$or": [{"tenant_id": str(tid)}, {"tenantId": str(tid)}]}
        if "$and" in query:
            query["$and"].append(tenant_filter)
        elif "$or" in query:
            existing_or = query.pop("$or")
            query["$and"] = [{"$or": existing_or}, tenant_filter]
        else:
            query["$or"] = tenant_filter["$or"]

    skip = (page - 1) * limit
    total = col.count_documents(query)
    cursor = col.find(query).skip(skip).limit(limit)
    items = [_doc_to_response(doc) for doc in cursor]

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# 2. Create vehicle  (POST /)
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create vehicle")
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_vehicle(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    # ---- Step 0: Basic Details ----
    make_model: str = Form(..., alias="makeModel", max_length=120),
    registration: str = Form(..., max_length=20),
    year: int = Form(..., ge=2000, le=2030),
    type: str = Form(...),
    fuel: str = Form(...),
    transmission: str = Form(...),
    registration_number: Optional[str] = Form(default=None, alias="registrationNumber"),
    color: Optional[str] = Form(default=None, max_length=60),
    engine_capacity: Optional[int] = Form(default=None, alias="engineCapacity"),
    seats: int = Form(default=1, ge=1, le=10),
    rc_status: str = Form(default="Pending review", alias="rcStatus"),
    trim: Optional[str] = Form(default=None, max_length=80),
    # ---- Step 1: Pricing & Availability ----
    daily_rate: float = Form(..., alias="dailyRate", ge=1.0),
    minimum_days: int = Form(default=1, alias="minimumDays", ge=1, le=365),
    security_deposit: float = Form(default=0.0, alias="securityDeposit", ge=0.0),
    pickup_address: str = Form(..., alias="pickupAddress", max_length=200),
    pickup_lat: Optional[float] = Form(default=None, alias="pickupLat"),
    pickup_lng: Optional[float] = Form(default=None, alias="pickupLng"),
    pickup_notes: Optional[str] = Form(default=None, alias="pickupNotes", max_length=500),
    show_on_wavygo: bool = Form(default=False, alias="showOnWavygo"),
    fleet_availability: str = Form(default="Available", alias="fleetAvailability"),
    # ---- Media ----
    photos: list[UploadFile] = [],
    documents: list[UploadFile] = [],
    document_types: list[str] = Form(default=[], alias="documentTypes"),
) -> dict:
    """
    Create a new vehicle.  Accepts multipart/form-data.

    Flat form fields cover all VehicleModel properties.
    ``photos[]``        — up to 20 vehicle photos (image/*)
    ``documents[]``     — up to 10 compliance documents (image/* or PDF)
    ``documentTypes[]`` — parallel array of DocumentType values (RC, Insurance, PUC, Other)
                          one per document file.

    Flow:
        1. Validate enum fields (type, fuel, transmission, fleetAvailability, docTypes)
        2. Normalise & deduplicate-check registrationNumber (409 on dup)
        3. Validate each uploaded file (MIME + size)
        4. Upload photos then documents to Cloudinary (plain blocking call via def handler)
        5. On any mid-upload failure, delete already-uploaded files (rollback)
        6. Build VehicleModel, set price=dailyRate, status mirrors showOnWavygo
        7. Insert into MongoDB; on failure delete all uploaded files (rollback)
        8. Return the created document
    """
    # ------------------------------------------------------------------
    # 1. Validate enum inputs
    # ------------------------------------------------------------------
    from app.modules.vehicles.models import (
        FuelType,
        RcStatus,
        TransmissionType,
    )

    def _check_enum(value: str, enum_cls, field_name: str) -> Any:
        try:
            return enum_cls(value)
        except ValueError:
            allowed = [e.value for e in enum_cls]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid {field_name} '{value}'. Allowed: {allowed}.",
            )

    type_enum = _check_enum(type, VehicleType, "type")
    fuel_enum = _check_enum(fuel, FuelType, "fuel")
    transmission_enum = _check_enum(transmission, TransmissionType, "transmission")
    fleet_avail_enum = _check_enum(fleet_availability, FleetAvailability, "fleetAvailability")
    rc_status_enum = _check_enum(rc_status, RcStatus, "rcStatus")

    # Keep the multipart route aligned with the Phase 1 Pydantic contract.
    # Files are validated separately below; this validates all scalar fields.
    try:
        VehicleCreateSchema.model_validate(
            {
                "makeModel": make_model,
                "trim": trim,
                "registration": registration,
                "registrationNumber": registration_number,
                "year": year,
                "type": type_enum.value,
                "fuel": fuel_enum.value,
                "color": color,
                "engineCapacity": engine_capacity,
                "rcStatus": rc_status_enum.value,
                "seats": seats,
                "transmission": transmission_enum.value,
                "dailyRate": daily_rate,
                "minimumDays": minimum_days,
                "securityDeposit": security_deposit,
                "pickupLocation": {
                    "address": pickup_address,
                    "lat": pickup_lat,
                    "lng": pickup_lng,
                },
                "pickupNotes": pickup_notes,
                "showOnWavygo": show_on_wavygo,
                "fleetAvailability": fleet_avail_enum.value,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            #detail=exc.errors(),
            detail=exc.errors(include_context=False),
        )

    # Validate document type labels
    if len(document_types) != len(documents):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"documentTypes must have one entry per document file. "
                f"Got {len(document_types)} types for {len(documents)} files."
            ),
        )
    doc_type_enums: list[DocumentType] = []
    for dt in document_types:
        doc_type_enums.append(_check_enum(dt, DocumentType, "documentType"))

    # ------------------------------------------------------------------
    # 2. RC normalise & duplicate check
    # ------------------------------------------------------------------
    norm_rc: Optional[str] = None
    rc_input = (registration_number or registration or "").strip()
    if rc_input:
        norm_rc = normalise_rc(rc_input)
        if norm_rc and not validate_rc_format(norm_rc):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{rc_input}' does not match the expected "
                    "registration number format (e.g. GJ05AB4821)."
                ),
            )
    if norm_rc:
        col = _get_vehicles_col()
        tid = _extract_tenant_id(tenant)
        if check_rc_duplicate(norm_rc, col, tenant_id=tid):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A vehicle with registration number '{norm_rc}' already exists. "
                    "Each vehicle must have a unique registration number."
                ),
            )

    # ------------------------------------------------------------------
    # 3. Validate uploaded files (MIME + size) before any Cloudinary call
    # ------------------------------------------------------------------
    if len(photos) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A vehicle may have at most 20 photos.",
        )
    if len(documents) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A vehicle may have at most 10 documents.",
        )

    for photo in photos:
        _validate_file_inline(photo, ALLOWED_PHOTO_MIME_TYPES, MAX_PHOTO_SIZE_BYTES, "photo")
    for doc in documents:
        _validate_file_inline(doc, ALLOWED_DOCUMENT_MIME_TYPES, MAX_DOCUMENT_SIZE_BYTES, "document")

    # ------------------------------------------------------------------
    # 4 & 5. Upload to Cloudinary with rollback on failure
    # ------------------------------------------------------------------
    uploaded_photos: list[VehiclePhoto] = []       # built progressively
    uploaded_docs: list[VehicleFile] = []
    # Track all raw metadata for rollback
    rollback_meta: list[dict] = []

    try:
        for photo in photos:
            file_bytes = photo.file.read()
            result = cloudinary_service.upload_file(
                file_bytes,
                folder=_CLOUDINARY_PHOTO_FOLDER,
                resource_type="image",
            )
            rollback_meta.append({"publicId": result["public_id"], "resourceType": "image"})
            uploaded_photos.append(
                VehiclePhoto(url=result["url"], publicId=result["public_id"])
            )

        for doc_file, doc_type in zip(documents, doc_type_enums):
            file_bytes = doc_file.file.read()
            rtype = _cloudinary_resource_type(doc_file.content_type or "image/jpeg")
            result = cloudinary_service.upload_file(
                file_bytes,
                folder=_CLOUDINARY_DOCUMENT_FOLDER,
                resource_type=rtype,
            )
            rollback_meta.append({"publicId": result["public_id"], "resourceType": rtype})
            uploaded_docs.append(
                VehicleFile(
                    type=doc_type,
                    url=result["url"],
                    publicId=result["public_id"],
                    resourceType=rtype,
                )
            )
    except HTTPException:
        _delete_cloudinary_files(rollback_meta)
        raise
    except Exception as exc:
        logger.error("Cloudinary upload failed during vehicle create: %s", exc)
        _delete_cloudinary_files(rollback_meta)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="File upload failed. Please try again.",
        )

    # ------------------------------------------------------------------
    # 6. Build the document
    # ------------------------------------------------------------------
    now = _now_utc()
    show = show_on_wavygo
    listing_status = ListingStatus.online if show else ListingStatus.offline

    from app.modules.vehicles.models import PickupLocation

    pickup_loc = PickupLocation(
        address=pickup_address,
        lat=pickup_lat,
        lng=pickup_lng,
    )

    vehicle = VehicleModel(
        name=make_model,
        registration=registration,
        type=type_enum,
        fuel=fuel_enum,
        year=year,
        color=color or "",
        engineCapacity=engine_capacity,
        rcStatus=rc_status_enum,
        seats=seats,
        transmission=transmission_enum,
        status=listing_status,
        # price and dailyRate must always be in sync
        price=daily_rate,
        dailyRate=daily_rate,
        minimumDays=minimum_days,
        securityDeposit=security_deposit,
        pickupLocation=pickup_loc,
        pickupNotes=pickup_notes or "",
        showOnWavygo=show,
        fleetAvailability=fleet_avail_enum,
        registrationNumber=norm_rc,
        photos=uploaded_photos,
        documents=uploaded_docs,
        createdAt=now,
        updatedAt=now,
    )

    doc = vehicle.model_dump(by_alias=True)
    tid = _extract_tenant_id(tenant)
    if tid:
        doc["tenant_id"] = str(tid)
        doc["tenantId"] = str(tid)

    # ------------------------------------------------------------------
    # 7. Insert into MongoDB; rollback Cloudinary on failure
    # ------------------------------------------------------------------
    # Remove registrationNumber if None so MongoDB sparse unique index does not index null
    if doc.get("registrationNumber") is None:
        doc.pop("registrationNumber", None)

    col = _get_vehicles_col()
    try:
        result_insert = col.insert_one(doc)
    except DuplicateKeyError:
        _delete_cloudinary_files(rollback_meta)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A vehicle with this registration number already exists.",
        )
    except Exception as exc:
        logger.error("MongoDB insert failed during vehicle create: %s", exc)
        _delete_cloudinary_files(rollback_meta)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save vehicle. Uploaded files have been removed.",
        )

    doc["id"] = str(result_insert.inserted_id)
    doc.pop("_id", None)

    try:
        from app.modules.notifications.service import create_notification
        create_notification(
            title="Vehicle Added",
            message=f"{vehicle.name} ({vehicle.registration}) added to fleet.",
            notification_type="vehicle",
            severity="success",
            entity_id=doc["id"],
            entity_type="vehicle",
            tenant_id=_extract_tenant_id(tenant),
        )
    except Exception:
        pass

    return doc


# ---------------------------------------------------------------------------
# 3. Get vehicle details  (fixed path before /{id})
# ---------------------------------------------------------------------------


@router.get("/{vehicle_id}", summary="Get vehicle by ID")
def get_vehicle(
    vehicle_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Return full vehicle details including photos and documents.
    Returns 404 for a missing vehicle.
    """
    col = _get_vehicles_col()
    doc = col.find_one(_vehicle_query(vehicle_id, tenant))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    return _doc_to_response(doc)


# ---------------------------------------------------------------------------
# 4. Update vehicle  (PATCH /{id})
# ---------------------------------------------------------------------------


@router.patch("/{vehicle_id}", summary="Update vehicle")
@router.put("/{vehicle_id}", summary="Update vehicle (PUT alias)")
def update_vehicle(
    vehicle_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    # Basic Details (all optional for PATCH)
    make_model: Optional[str] = Form(default=None, alias="makeModel", max_length=120),
    registration: Optional[str] = Form(default=None, max_length=20),
    year: Optional[int] = Form(default=None, ge=2000, le=2030),
    type: Optional[str] = Form(default=None),
    fuel: Optional[str] = Form(default=None),
    transmission: Optional[str] = Form(default=None),
    registration_number: Optional[str] = Form(default=None, alias="registrationNumber"),
    color: Optional[str] = Form(default=None, max_length=60),
    engine_capacity: Optional[int] = Form(default=None, alias="engineCapacity"),
    seats: Optional[int] = Form(default=None, ge=1, le=10),
    rc_status: Optional[str] = Form(default=None, alias="rcStatus"),
    trim: Optional[str] = Form(default=None, max_length=80),
    # Pricing & Availability
    daily_rate: Optional[float] = Form(default=None, alias="dailyRate", ge=1.0),
    minimum_days: Optional[int] = Form(default=None, alias="minimumDays", ge=1, le=365),
    security_deposit: Optional[float] = Form(default=None, alias="securityDeposit", ge=0.0),
    pickup_address: Optional[str] = Form(default=None, alias="pickupAddress", max_length=200),
    pickup_lat: Optional[float] = Form(default=None, alias="pickupLat"),
    pickup_lng: Optional[float] = Form(default=None, alias="pickupLng"),
    pickup_notes: Optional[str] = Form(default=None, alias="pickupNotes", max_length=500),
    show_on_wavygo: Union[bool, str, None] = Form(default=None, alias="showOnWavygo"),
    fleet_availability: Optional[str] = Form(default=None, alias="fleetAvailability"),
    # Media — new files to add
    new_photos: list[UploadFile] = [],
    new_documents: list[UploadFile] = [],
    new_document_types: list[str] = Form(default=[], alias="newDocumentTypes"),
    # Public IDs of existing photos/documents to remove
    remove_photo_ids: list[str] = Form(default=[], alias="removePhotoIds"),
    remove_document_ids: list[str] = Form(default=[], alias="removeDocumentIds"),
) -> dict:
    """
    Partially update a vehicle (PATCH semantics — only send changed fields).

    Media management:
    - ``newPhotos[]`` + ``newDocumentTypes[]`` / ``newDocuments[]`` — files to add.
    - ``removePhotoIds[]``    — publicId values of photos to remove.
    - ``removeDocumentIds[]`` — publicId values of documents to remove.

    Cloudinary deletions of removed files happen AFTER the DB update succeeds.
    If DB update fails, no Cloudinary files are removed.
    """
    from app.modules.vehicles.models import (
        FuelType,
        RcStatus,
        TransmissionType,
    )

    col = _get_vehicles_col()
    existing = col.find_one(_vehicle_query(vehicle_id, tenant))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    oid = existing["_id"]
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )

    # Parse show_on_wavygo only if provided (missing form fields must remain None)
    parsed_show_on_wavygo: Optional[bool] = None
    if show_on_wavygo is not None:
        if isinstance(show_on_wavygo, bool):
            parsed_show_on_wavygo = show_on_wavygo
        elif isinstance(show_on_wavygo, str):
            s = show_on_wavygo.strip().lower()
            if s in ("true", "1", "yes", "on"):
                parsed_show_on_wavygo = True
            elif s in ("false", "0", "no", "off"):
                parsed_show_on_wavygo = False

    # Validate supplied scalar fields through the Phase 1 update schema.
    # When only part of the pickup location changes, merge it with its stored
    # counterpart first so the schema can enforce a valid lat/lng pair.
    existing_loc = existing.get("pickupLocation", {}) or {}
    schema_payload: dict[str, Any] = {
        key: value
        for key, value in {
            "makeModel": make_model,
            "trim": trim,
            "registration": registration,
            "registrationNumber": registration_number,
            "year": year,
            "type": type,
            "fuel": fuel,
            "color": color,
            "engineCapacity": engine_capacity,
            "rcStatus": rc_status,
            "seats": seats,
            "transmission": transmission,
            "dailyRate": daily_rate,
            "minimumDays": minimum_days,
            "securityDeposit": security_deposit,
            "pickupNotes": pickup_notes,
            "showOnWavygo": parsed_show_on_wavygo,
            "fleetAvailability": fleet_availability,
        }.items()
        if value is not None
    }
    if any(value is not None for value in (pickup_address, pickup_lat, pickup_lng)):
        schema_payload["pickupLocation"] = {
            "address": pickup_address if pickup_address is not None else existing_loc.get("address", ""),
            "lat": pickup_lat if pickup_lat is not None else existing_loc.get("lat"),
            "lng": pickup_lng if pickup_lng is not None else existing_loc.get("lng"),
        }
    try:
        VehicleUpdateSchema.model_validate(schema_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        )

    # ------------------------------------------------------------------
    # Build the $set payload — only include fields that were provided
    # ------------------------------------------------------------------
    set_doc: dict[str, Any] = {}

    def _check_enum(value: Optional[str], enum_cls, field_name: str) -> Any:
        if value is None:
            return None
        try:
            return enum_cls(value)
        except ValueError:
            allowed = [e.value for e in enum_cls]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid {field_name} '{value}'. Allowed: {allowed}.",
            )

    if make_model is not None:
        set_doc["name"] = make_model
    if registration is not None:
        set_doc["registration"] = registration
    if year is not None:
        set_doc["year"] = year
    if color is not None:
        set_doc["color"] = color
    if engine_capacity is not None:
        set_doc["engineCapacity"] = engine_capacity
    if seats is not None:
        set_doc["seats"] = seats
    if trim is not None:
        set_doc["trim"] = trim
    if pickup_notes is not None:
        set_doc["pickupNotes"] = pickup_notes

    type_enum = _check_enum(type, VehicleType, "type")
    if type_enum is not None:
        set_doc["type"] = type_enum.value

    fuel_enum = _check_enum(fuel, FuelType, "fuel")
    if fuel_enum is not None:
        set_doc["fuel"] = fuel_enum.value

    transmission_enum = _check_enum(transmission, TransmissionType, "transmission")
    if transmission_enum is not None:
        set_doc["transmission"] = transmission_enum.value

    rc_status_enum = _check_enum(rc_status, RcStatus, "rcStatus")
    if rc_status_enum is not None:
        set_doc["rcStatus"] = rc_status_enum.value

    fleet_avail_enum = _check_enum(fleet_availability, FleetAvailability, "fleetAvailability")
    if fleet_avail_enum is not None:
        # FIX: Forbid manual change to Available/Rented if vehicle is under maintenance or active rental
        if fleet_avail_enum.value in ("Available", "Rented") and _operational_state_change_is_blocked(existing, tenant):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle availability cannot be changed while maintenance or an active rental is open.",
            )
        # FIX: Keep fleetAvailability and availability in sync
        set_doc["fleetAvailability"] = fleet_avail_enum.value
        set_doc["availability"] = fleet_avail_enum.value

    # dailyRate + price must move together (rule 1)
    if daily_rate is not None:
        set_doc["dailyRate"] = daily_rate
        set_doc["price"] = daily_rate
    if minimum_days is not None:
        set_doc["minimumDays"] = minimum_days
    if security_deposit is not None:
        set_doc["securityDeposit"] = security_deposit

    # showOnWavygo + status must move together (rule 2)
    if parsed_show_on_wavygo is not None:
        set_doc["showOnWavygo"] = parsed_show_on_wavygo
        set_doc["status"] = (
            ListingStatus.online.value if parsed_show_on_wavygo else ListingStatus.offline.value
        )

    # Pickup location may be patched one field at a time.
    if any(value is not None for value in (pickup_address, pickup_lat, pickup_lng)):
        set_doc["pickupLocation"] = {
            "address": pickup_address if pickup_address is not None else existing_loc.get("address", ""),
            "lat": pickup_lat if pickup_lat is not None else existing_loc.get("lat"),
            "lng": pickup_lng if pickup_lng is not None else existing_loc.get("lng"),
        }

    # ------------------------------------------------------------------
    # RC duplicate check if changing registrationNumber
    # ------------------------------------------------------------------
    norm_rc: Optional[str] = None
    rc_update = registration_number if registration_number is not None else registration
    if rc_update is not None:
        norm_rc = normalise_rc(rc_update)
        if norm_rc and not validate_rc_format(norm_rc):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{rc_update}' does not match the expected "
                    "registration number format."
                ),
            )
        if norm_rc:
            existing_rc = existing.get("registrationNumber")
            tid = _extract_tenant_id(tenant)
            if norm_rc != existing_rc and check_rc_duplicate(norm_rc, col, tenant_id=tid):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"A vehicle with registration number '{norm_rc}' already exists."
                    ),
                )
            set_doc["registrationNumber"] = norm_rc

    # ------------------------------------------------------------------
    # Validate document types for new uploads
    # ------------------------------------------------------------------
    if len(new_document_types) != len(new_documents):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"newDocumentTypes must have one entry per new document file. "
                f"Got {len(new_document_types)} types for {len(new_documents)} files."
            ),
        )
    new_doc_type_enums: list[DocumentType] = []
    for dt in new_document_types:
        new_doc_type_enums.append(_check_enum(dt, DocumentType, "documentType"))

    # ------------------------------------------------------------------
    # Validate new files before any upload
    # ------------------------------------------------------------------
    for photo in new_photos:
        _validate_file_inline(photo, ALLOWED_PHOTO_MIME_TYPES, MAX_PHOTO_SIZE_BYTES, "photo")
    for doc in new_documents:
        _validate_file_inline(doc, ALLOWED_DOCUMENT_MIME_TYPES, MAX_DOCUMENT_SIZE_BYTES, "document")

    # ------------------------------------------------------------------
    # Upload new files to Cloudinary
    # ------------------------------------------------------------------
    newly_uploaded: list[dict] = []  # for rollback
    new_photo_models: list[dict] = []
    new_doc_models: list[dict] = []

    try:
        for photo in new_photos:
            file_bytes = photo.file.read()
            result = cloudinary_service.upload_file(
                file_bytes, folder=_CLOUDINARY_PHOTO_FOLDER, resource_type="image"
            )
            newly_uploaded.append({"publicId": result["public_id"], "resourceType": "image"})
            new_photo_models.append({
                "url": result["url"],
                "publicId": result["public_id"],
            })

        for doc_file, doc_type in zip(new_documents, new_doc_type_enums):
            file_bytes = doc_file.file.read()
            rtype = _cloudinary_resource_type(doc_file.content_type or "image/jpeg")
            result = cloudinary_service.upload_file(
                file_bytes, folder=_CLOUDINARY_DOCUMENT_FOLDER, resource_type=rtype
            )
            newly_uploaded.append({"publicId": result["public_id"], "resourceType": rtype})
            new_doc_models.append({
                "type": doc_type.value,
                "url": result["url"],
                "publicId": result["public_id"],
                "resourceType": rtype,
                "uploadedAt": _now_utc().isoformat(),
            })
    except HTTPException:
        _delete_cloudinary_files(newly_uploaded)
        raise
    except Exception as exc:
        logger.error("Cloudinary upload failed during vehicle update: %s", exc)
        _delete_cloudinary_files(newly_uploaded)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="File upload failed. Please try again.",
        )

    # ------------------------------------------------------------------
    # Build the final media arrays and persist them atomically with fields.
    # This avoids a partially-updated vehicle if one of several array writes
    # fails after new files have reached Cloudinary.
    # ------------------------------------------------------------------
    existing_photos = [p for p in (existing.get("photos", []) or []) if isinstance(p, dict)]
    existing_docs = [d for d in (existing.get("documents", []) or []) if isinstance(d, dict)]
    photo_ids_to_remove = {pid for pid in remove_photo_ids if pid}
    document_ids_to_remove = {pid for pid in remove_document_ids if pid}
    removed_photos = [p for p in existing_photos if p.get("publicId") in photo_ids_to_remove]
    removed_docs = [d for d in existing_docs if d.get("publicId") in document_ids_to_remove]
    final_photos = [p for p in existing_photos if p.get("publicId") not in photo_ids_to_remove] + new_photo_models
    final_docs = [d for d in existing_docs if d.get("publicId") not in document_ids_to_remove] + new_doc_models

    if len(final_photos) > 20:
        _delete_cloudinary_files(newly_uploaded)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A vehicle may have at most 20 photos.",
        )
    if len(final_docs) > 10:
        _delete_cloudinary_files(newly_uploaded)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A vehicle may have at most 10 documents.",
        )

    set_doc["updatedAt"] = _now_utc()
    if remove_photo_ids or new_photo_models:
        set_doc["photos"] = final_photos
    if remove_document_ids or new_doc_models:
        set_doc["documents"] = final_docs

    try:
        col.update_one({"_id": oid}, {"$set": set_doc})

    except DuplicateKeyError:
        _delete_cloudinary_files(newly_uploaded)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A vehicle with this registration number already exists.",
        )
    except Exception as exc:
        logger.error("MongoDB update failed during vehicle update: %s", exc)
        # Rollback newly uploaded Cloudinary files since DB update failed
        _delete_cloudinary_files(newly_uploaded)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vehicle.",
        )

    # ------------------------------------------------------------------
    # Delete REMOVED Cloudinary files AFTER successful DB update
    # ------------------------------------------------------------------
    _delete_cloudinary_files(
        [{"publicId": p.get("publicId"), "resourceType": "image"} for p in removed_photos]
        + [
            {"publicId": d.get("publicId"), "resourceType": d.get("resourceType", "image")}
            for d in removed_docs
        ]
    )

    updated_doc = col.find_one({"_id": oid}) or existing

    try:
        from app.modules.notifications.service import create_notification
        prev_avail = existing.get("fleetAvailability") or existing.get("availability")
        new_avail = set_doc.get("fleetAvailability")
        prev_status = existing.get("status")
        new_status = set_doc.get("status")
        v_name = existing.get("makeModel") or existing.get("name") or vehicle_id
        v_reg = existing.get("registration") or ""

        if new_avail and new_avail != prev_avail:
            create_notification(
                title="Vehicle Status Changed",
                message=f"{v_name} ({v_reg}) status updated to '{new_avail}'.",
                notification_type="vehicle",
                severity="info" if new_avail == "Available" else "warning",
                entity_id=str(vehicle_id),
                entity_type="vehicle",
                tenant_id=_extract_tenant_id(tenant) or existing.get("tenant_id") or existing.get("tenantId") or existing.get("vendor_id"),
            )
        elif new_status and new_status != prev_status:
            create_notification(
                title="Vehicle Visibility Changed",
                message=f"{v_name} ({v_reg}) status is now {new_status}.",
                notification_type="vehicle",
                severity="info",
                entity_id=str(vehicle_id),
                entity_type="vehicle",
                tenant_id=_extract_tenant_id(tenant) or existing.get("tenant_id") or existing.get("tenantId") or existing.get("vendor_id"),
            )
    except Exception:
        pass

    return _doc_to_response(updated_doc)


# ---------------------------------------------------------------------------
# 7. Toggle show-on-wavygo  (fixed path before /{id} catch-all)
# NOTE: declared before the plain PATCH /{vehicle_id} so FastAPI's router
# matches /show-on-wavygo correctly.
# ---------------------------------------------------------------------------


@router.patch("/{vehicle_id}/show-on-wavygo", summary="Toggle show on WavyGo")
def toggle_show_on_wavygo(
    vehicle_id: str,
    payload: ShowOnWavygoSchema,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Set ``showOnWavygo`` and mirror the change to ``status``.

    Sets:
        showOnWavygo → provided value
        status       → "Online" if showOnWavygo else "Offline"

    Does NOT touch ``fleetAvailability`` / ``availability`` (rule 3).
    """
    col = _get_vehicles_col()
    existing = col.find_one(_vehicle_query(vehicle_id, tenant))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    oid = existing["_id"]

    show_on_wavygo = payload.show_on_wavygo
    listing_status = ListingStatus.online.value if show_on_wavygo else ListingStatus.offline.value
    col.update_one(
        {"_id": oid},
        {
            "$set": {
                "showOnWavygo": show_on_wavygo,
                "status": listing_status,
                "updatedAt": _now_utc().isoformat(),
            }
        },
    )
    updated = col.find_one({"_id": oid}) or existing

    try:
        from app.modules.notifications.service import create_notification
        v_name = existing.get("makeModel") or existing.get("name") or vehicle_id
        create_notification(
            title="Vehicle Visibility Changed",
            message=f"{v_name} is now {listing_status} on WavyGo marketplace.",
            notification_type="vehicle",
            severity="info",
            entity_id=str(vehicle_id),
            entity_type="vehicle",
            tenant_id=_extract_tenant_id(tenant) or existing.get("tenant_id") or existing.get("tenantId") or existing.get("vendor_id"),
        )
    except Exception:
        pass

    return _doc_to_response(updated)


# ---------------------------------------------------------------------------
# 5. Delete vehicle  (DELETE /{id})
# ---------------------------------------------------------------------------


@router.delete("/{vehicle_id}", status_code=status.HTTP_200_OK, summary="Delete vehicle")
def delete_vehicle(
    vehicle_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Delete a vehicle.

    Returns 404 if not found, 409 if active bookings reference this vehicle.
    Cloudinary files are deleted AFTER the DB record is removed.
    """
    col = _get_vehicles_col()
    existing = col.find_one(_vehicle_query(vehicle_id, tenant))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    oid = existing["_id"]

    # ------------------------------------------------------------------
    # Check for booking references before deleting
    # Bookings may reference vehicles by ObjectId or string id.
    # We check both to be safe.
    # ------------------------------------------------------------------
    try:
        bookings_col = _get_bookings_col()
        booking_exists = bookings_col.find_one(
            {"$or": [{"vehicleId": oid}, {"vehicleId": vehicle_id}]}
        )
        if booking_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot delete this vehicle because it has active booking records. "
                    "Cancel or reassign all bookings before deleting the vehicle."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        # bookings collection might not exist yet — treat as no bookings
        pass

    # ------------------------------------------------------------------
    # Delete the DB record first
    # ------------------------------------------------------------------
    col.delete_one({"_id": oid})

    try:
        from app.modules.notifications.service import create_notification
        v_name = existing.get("makeModel") or existing.get("name") or vehicle_id
        create_notification(
            title="Vehicle Deleted",
            message=f"{v_name} was removed from your fleet.",
            notification_type="vehicle",
            severity="warning",
            entity_id=str(vehicle_id),
            entity_type="vehicle",
            tenant_id=_extract_tenant_id(tenant) or existing.get("tenant_id") or existing.get("tenantId") or existing.get("vendor_id"),
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Delete Cloudinary files after successful DB removal
    # ------------------------------------------------------------------
    photos: list[dict] = existing.get("photos", []) or []
    documents: list[dict] = existing.get("documents", []) or []

    photo_meta = [
        {"publicId": p.get("publicId"), "resourceType": "image"}
        for p in photos
        if isinstance(p, dict) and p.get("publicId")
    ]
    doc_meta = [
        {
            "publicId": d.get("publicId"),
            "resourceType": d.get("resourceType", "image"),
        }
        for d in documents
        if isinstance(d, dict) and d.get("publicId")
    ]

    _delete_cloudinary_files(photo_meta + doc_meta)

    return {"message": f"Vehicle '{vehicle_id}' deleted successfully.", "id": vehicle_id}
