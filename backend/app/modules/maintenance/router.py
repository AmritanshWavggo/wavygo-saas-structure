from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.modules.auth.security import get_optional_vendor
from app.modules.maintenance.schemas import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceResponse,
    MaintenanceStatsResponse,
    VehicleReviewStatusUpdate,
)
from app.modules.maintenance.service import maintenance_service

router = APIRouter()


def _get_tenant_id(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            from app.modules.auth.security import decode_access_token
            claims = decode_access_token(token)
            if claims.get("sub"):
                return str(claims["sub"])
        except Exception:
            pass
    vendor = get_optional_vendor(request)
    return str(vendor["_id"]) if vendor and "_id" in vendor else None


@router.post(
    "",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add vehicle to maintenance",
    description="Records a new maintenance job with damage/flaw details, start date, cost, and sets vehicle status to Maintenance.",
)
def create_maintenance(payload: MaintenanceCreate, request: Request) -> MaintenanceResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return maintenance_service.create_maintenance(payload, tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to record maintenance: {str(exc)}",
        )


@router.get(
    "",
    response_model=List[MaintenanceResponse],
    summary="List maintenance jobs",
    description="Retrieve all maintenance records with optional status, vehicle, and search filters.",
)
def list_maintenance(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: Ongoing, Completed, or All"),
    vehicle_id: Optional[str] = Query(None, description="Filter by vehicle ID or name"),
    query: Optional[str] = Query(None, description="Search by ID, vehicle, type, mechanic or damage"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[MaintenanceResponse]:
    tenant_id = _get_tenant_id(request)
    return maintenance_service.list_maintenance(
        status=status,
        vehicle_id=vehicle_id,
        query=query,
        skip=skip,
        limit=limit,
        tenant_id=tenant_id,
    )


@router.get(
    "/stats",
    response_model=MaintenanceStatsResponse,
    summary="Get maintenance statistics",
    description="Retrieve live count of vehicles currently in maintenance, ongoing jobs, and total spend.",
)
def get_maintenance_stats(request: Request) -> MaintenanceStatsResponse:
    tenant_id = _get_tenant_id(request)
    return maintenance_service.get_stats(tenant_id=tenant_id)


@router.get(
    "/{record_id}",
    response_model=MaintenanceResponse,
    summary="Get maintenance job details",
)
def get_maintenance(record_id: str, request: Request) -> MaintenanceResponse:
    tenant_id = _get_tenant_id(request)
    record = maintenance_service.get_maintenance(record_id, tenant_id=tenant_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record '{record_id}' not found.",
        )
    return record


@router.patch(
    "/{record_id}",
    response_model=MaintenanceResponse,
    summary="Update maintenance record",
    description="Update status (Ongoing to Completed), mechanic notes, cost, or completed date.",
)
def update_maintenance(record_id: str, payload: MaintenanceUpdate, request: Request) -> MaintenanceResponse:
    tenant_id = _get_tenant_id(request)
    updated = maintenance_service.update_maintenance(record_id, payload, tenant_id=tenant_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record '{record_id}' not found.",
        )
    return updated


@router.post(
    "/{record_id}/complete",
    response_model=MaintenanceResponse,
    summary="Complete maintenance job",
)
def complete_maintenance(record_id: str, request: Request) -> MaintenanceResponse:
    res = maintenance_service.complete_maintenance(record_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record '{record_id}' not found.",
        )
    return res


@router.post("/vehicle-status", summary="Update vehicle review status (POST)")
def update_vehicle_status_post(payload: VehicleReviewStatusUpdate, request: Request) -> Dict[str, Any]:
    return maintenance_service.update_vehicle_review_status(payload)


@router.patch(
    "/vehicles/{vehicle_id}/review-status",
    summary="Update vehicle RC / Fleet review status",
    description="Updates vehicle review status (e.g., Pending review, Approved, Rejected).",
)
def update_vehicle_review_status(vehicle_id: str, payload: VehicleReviewStatusUpdate, request: Request) -> Dict[str, Any]:
    return maintenance_service.update_vehicle_review_status(vehicle_id, payload.status)
