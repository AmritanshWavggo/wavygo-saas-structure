from __future__ import annotations

from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator


class MaintenanceCreate(BaseModel):
    vehicle_id: Optional[str] = Field(None, description="Vehicle ID e.g. VH-1042")
    vehicle: str = Field(..., description="Vehicle name e.g. Honda Activa 6G")
    registration: Optional[str] = Field(None, description="Registration number e.g. GJ 05 AB 4821")
    type: str = Field("Damage Repair", description="Maintenance type e.g. Damage Repair, Brake inspection, Scheduled servicing")
    damage_details: Optional[str] = Field(None, description="Description of the flaw, damage, or issue identified during review")
    issue: Optional[str] = Field(None, description="Short summary of issue")
    start: str = Field(..., description="Start date e.g. 2026-10-30 or Oct 30, 2026")
    expected: Optional[str] = Field(None, description="Expected completion date")
    cost: float = Field(0.0, ge=0, description="Estimated or actual repair cost in INR")
    payment: Optional[str] = Field("Pending", description="Payment status: Pending or Paid")
    status: Optional[str] = Field("Ongoing", description="Maintenance work status: Ongoing or Completed")
    mechanic_name: Optional[str] = Field(None, description="Mechanic or workshop name")
    notes: Optional[str] = Field(None, description="Additional workshop or inspection notes")

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Vehicle aliases
            if "vehicle_name" in data and not data.get("vehicle"):
                data["vehicle"] = data["vehicle_name"]
            # Type aliases
            if "maintenance_type" in data and not data.get("type"):
                data["type"] = data["maintenance_type"]
            # Damage / issue aliases
            if "damage" in data and not data.get("damage_details"):
                data["damage_details"] = data["damage"]
            if "issue" in data and not data.get("damage_details"):
                data["damage_details"] = data["issue"]
            if data.get("damage_details") and not data.get("issue"):
                data["issue"] = data["damage_details"]
            # Amount / Cost aliases
            if "estimated_cost" in data and "cost" not in data:
                data["cost"] = data["estimated_cost"]
            if "amount" in data and "cost" not in data:
                data["cost"] = data["amount"]
            # Payment status aliases
            if "payment_status" in data and not data.get("payment"):
                data["payment"] = data["payment_status"]
            # Date aliases
            if "start_date" in data and not data.get("start"):
                data["start"] = data["start_date"]
            if "expected_date" in data and not data.get("expected"):
                data["expected"] = data["expected_date"]
        return data


class MaintenanceUpdate(BaseModel):
    type: Optional[str] = Field(None, description="Maintenance type")
    damage_details: Optional[str] = Field(None, description="Damage details")
    issue: Optional[str] = Field(None, description="Issue description")
    start: Optional[str] = Field(None, description="Start date")
    expected: Optional[str] = Field(None, description="Expected date")
    cost: Optional[float] = Field(None, ge=0, description="Cost in INR")
    payment: Optional[str] = Field(None, description="Payment status: Pending or Paid")
    status: Optional[str] = Field(None, description="Work status: Ongoing or Completed")
    mechanic_name: Optional[str] = Field(None, description="Mechanic name")
    notes: Optional[str] = Field(None, description="Notes")


class VehicleReviewStatusUpdate(BaseModel):
    vehicle_id: str = Field(..., description="Vehicle ID e.g. VH-1042")
    status: str = Field(..., description="New availability status: Available, Under Review, Maintenance, Rented")
    notes: Optional[str] = Field(None, description="Inspection or review notes")


class MaintenanceResponse(BaseModel):
    id: str = Field(..., description="Maintenance ID e.g. MT-082")
    vehicle_id: Optional[str] = None
    vehicle: str
    registration: Optional[str] = None
    type: str
    damage_details: Optional[str] = None
    issue: Optional[str] = None
    start: str
    expected: Optional[str] = None
    cost: float
    payment: str = "Pending"
    status: str = "Ongoing"
    mechanic_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class MaintenanceStatsResponse(BaseModel):
    open_jobs: int
    completed_jobs: int
    total_cost: float
    total_jobs: int
