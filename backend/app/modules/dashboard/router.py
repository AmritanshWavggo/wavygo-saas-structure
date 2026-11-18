from __future__ import annotations

from typing import Annotated, Any, Optional
from fastapi import APIRouter, Depends, Query, Request

from app.modules.auth.security import get_optional_vendor
from app.modules.dashboard.schemas import DashboardStatsResponse, UpcomingArrivalItem
from app.modules.dashboard.service import dashboard_service

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsResponse, summary="Get dashboard metrics and charts")
@router.get("", response_model=DashboardStatsResponse, summary="Get dashboard metrics (alias)", include_in_schema=False)
def get_dashboard_stats(
    range: Optional[str] = Query(default="Last 30 days", alias="range"),
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> DashboardStatsResponse:
    """
    Returns high-level fleet statistics, revenue numbers, utilization percentage,
    monthly trend data, and latest bookings for the partner dashboard.
    """
    tenant_id = str(vendor["_id"]) if vendor else None
    return dashboard_service.get_stats(date_range=range, tenant_id=tenant_id)


@router.get("/arrivals", response_model=list[UpcomingArrivalItem], summary="Get upcoming vehicle arrivals")
def get_upcoming_arrivals(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> list[UpcomingArrivalItem]:
    tenant_id = str(vendor["_id"]) if vendor else None
    return dashboard_service.get_upcoming_arrivals(tenant_id=tenant_id)


@router.patch("/arrivals/{booking_id}/arrive", summary="Mark upcoming vehicle arrival as arrived")
@router.post("/arrivals/{booking_id}/arrive", summary="Mark upcoming vehicle arrival as arrived (POST alias)")
def mark_vehicle_arrival(
    booking_id: str,
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, Any]:
    tenant_id = str(vendor["_id"]) if vendor and "_id" in vendor else None
    dashboard_service.mark_arrived(booking_id, tenant_id=tenant_id)
    return {"booking_id": booking_id, "status": "Arrived", "vehicle_status": "Under Review", "success": True}
