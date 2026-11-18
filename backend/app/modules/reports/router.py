from __future__ import annotations

from typing import Annotated, Any, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Request, Response

from app.modules.auth.security import get_optional_vendor
from app.modules.reports.schemas import (
    ReportSummaryResponse,
    ReportsFullResponse,
    TopVehicleItem,
    TrendItem,
    UtilizationByTypeItem,
)
from app.modules.reports.service import reports_service

router = APIRouter()


@router.get("/summary", response_model=ReportSummaryResponse, summary="Get high-level reports summary KPIs")
def get_reports_summary(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> ReportSummaryResponse:
    """Returns total revenue, active bookings, fleet utilization, customer count, and total fleet size."""
    tenant_id = str(vendor["_id"]) if vendor else None
    return reports_service.get_summary(tenant_id)


@router.get(
    "/utilization-by-type",
    response_model=List[UtilizationByTypeItem],
    summary="Get fleet utilization categorized by vehicle type",
)
def get_utilization_by_type(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> List[UtilizationByTypeItem]:
    """Returns utilization percentages and on-road counts grouped by vehicle type (Motorcycles, Scooters, Electric)."""
    tenant_id = str(vendor["_id"]) if vendor else None
    return reports_service.get_utilization_by_type(tenant_id)


@router.get(
    "/top-vehicles",
    response_model=List[TopVehicleItem],
    summary="Get top vehicles ranked by actual customer bookings",
)
def get_top_vehicles(
    limit: int = Query(default=5, ge=1, le=50),
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> List[TopVehicleItem]:
    """Returns top performing vehicles in fleet sorted by booking count and generated revenue."""
    tenant_id = str(vendor["_id"]) if vendor else None
    return reports_service.get_top_vehicles(tenant_id, limit=limit)


@router.get("/trend", response_model=List[TrendItem], summary="Get dynamic analytics trend data")
def get_trend(
    section: str = Query(default="Overview", description="Section: Overview, Bookings, Vehicles, Maintenance, Revenue"),
    range: str = Query(default="Last 6 months", alias="range"),
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> List[TrendItem]:
    """Returns monthly / periodic aggregated numbers for the specified analytics tab."""
    tenant_id = str(vendor["_id"]) if vendor else None
    return reports_service.get_trend(section=section, range_filter=range, tenant_id=tenant_id)


@router.get("/full", response_model=ReportsFullResponse, summary="Get full unified reports analytics payload")
def get_full_reports(
    range: str = Query(default="Last 6 months", alias="range"),
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> ReportsFullResponse:
    """Returns unified summary, utilization by type, top vehicles, and trend chart data."""
    tenant_id = str(vendor["_id"]) if vendor else None
    return reports_service.get_full_report(range_filter=range, tenant_id=tenant_id)


@router.get("/export/csv", summary="Export bookings data as CSV")
def export_csv(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> Response:
    """Generates and streams a downloadable CSV of all booking records."""
    tenant_id = str(vendor["_id"]) if vendor else None
    csv_data = reports_service.export_bookings_csv(tenant_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="wavygo-bookings-export.csv"'},
    )
