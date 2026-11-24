from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ReportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_revenue: float
    active_bookings: int
    fleet_utilization: int
    total_customers: int
    total_vehicles: int
    total_maintenance: int
    total_pending: float


class UtilizationByTypeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    total: int
    rented: int
    utilization_pct: int


class TopVehicleItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    registration: str
    type: str
    bookings_count: int
    revenue_generated: float


class TrendItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: float


class ReportsFullResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: ReportSummaryResponse
    utilization_by_type: List[UtilizationByTypeItem]
    top_vehicles: List[TopVehicleItem]
    trend: List[TrendItem]

