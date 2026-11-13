from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class RevenueTrendItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: float


class RecentBookingItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    customer: str
    vehicle: str
    dates: str
    status: str
    paid: float
    pending: float


class RentedVehicleItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    registration: str
    availability: str
    type: Optional[str] = None
    dailyRate: Optional[float] = None
    image: Optional[str] = None


class UpcomingArrivalItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bookingId: str
    vehicleId: str
    customerId: Optional[str] = None
    staffId: Optional[str] = None
    pickupLocation: str = ""
    returnLocation: str = ""
    expectedAt: float
    status: str = "Upcoming"
    vehicle: Optional[Dict[str, Any]] = None
    customer: Optional[Dict[str, Any]] = None
    staff: Optional[Dict[str, Any]] = None


class DashboardStatsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_vehicles: int
    available_vehicles: int
    rented_vehicles: int
    under_review_vehicles: int = 0
    active_bookings: int
    total_bookings: int
    total_revenue: float
    pending_payments: float
    fleet_utilization: int
    revenue_trend: List[RevenueTrendItem]
    recent_bookings: List[RecentBookingItem]
    rented_vehicles_list: List[RentedVehicleItem]
    upcoming_arrivals: List[UpcomingArrivalItem] = []

