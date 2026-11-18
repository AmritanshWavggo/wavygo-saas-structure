from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class ExpenseCreate(BaseModel):
    category: str = Field(..., description="Category: Maintenance, Fuel, Staff Salaries, Rent & Operations, Insurance & Taxes, Utilities, Marketing, Misc")
    title: str = Field(..., min_length=2, max_length=200, description="Expense title or description")
    amount: float = Field(..., gt=0, description="Expense amount in INR")
    date: Optional[str] = Field(None, description="Date formatted e.g. Oct 28, 2026 or 2026-10-28")
    payment_method: str = Field("UPI", description="Payment method: UPI, Cash, Bank Transfer, Card")
    payee: Optional[str] = Field(None, description="Vendor, service center, or recipient name")
    reference: Optional[str] = Field(None, description="Invoice, bill, or transaction reference number")
    status: str = Field("Paid", description="Status: Paid or Pending")
    notes: Optional[str] = Field(None, description="Additional notes or remarks")

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "description" in data and not data.get("title"):
                data["title"] = data["description"]
            if "method" in data and not data.get("payment_method"):
                data["payment_method"] = data["method"]
            if "vendor" in data and not data.get("payee"):
                data["payee"] = data["vendor"]
        return data


class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    date: Optional[str] = None
    payment_method: Optional[str] = None
    payee: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: str = Field(..., description="Expense ID e.g. EXP-101")
    category: str
    title: str
    amount: float
    date: str
    payment_method: str
    payee: Optional[str] = None
    reference: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class MonthlyFinanceData(BaseModel):
    label: str = Field(..., description="Month abbreviation e.g. May, Jun, Oct")
    month_number: int = Field(..., ge=1, le=12)
    year: int
    revenue: float = Field(..., description="Revenue in thousands (₹'000) or exact INR")
    expenses: float = Field(..., description="Expenses in thousands (₹'000) or exact INR")
    exact_revenue: float = Field(..., description="Exact revenue in INR")
    exact_expenses: float = Field(..., description="Exact expenses in INR")
    net_profit: float = Field(..., description="Net profit in INR")


class CategoryExpenseSummary(BaseModel):
    category: str
    amount: float
    percentage: float
    count: int


class FinanceOverviewResponse(BaseModel):
    total_revenue: float = Field(..., description="Total verified revenue collected")
    online_revenue: float = Field(..., description="Revenue collected via online / digital methods")
    offline_revenue: float = Field(..., description="Revenue collected via counter cash / direct UPI")
    pending_receivables: float = Field(..., description="Total outstanding customer dues from bookings")
    total_expenses: float = Field(..., description="Total operating + maintenance expenses")
    operating_expenses: float = Field(..., description="Fleet hub, rent, utilities, fuel, and staff expenses")
    maintenance_costs: float = Field(..., description="Total fleet repair, spare parts, and servicing costs")
    estimated_net: float = Field(..., description="Net earnings (total_revenue - total_expenses)")
    profit_margin_pct: float = Field(..., description="Net profit margin percentage")
    comparison_chart: List[MonthlyFinanceData] = Field(..., description="Monthly trend for revenue vs expenses")
    expense_breakdown: List[CategoryExpenseSummary] = Field(..., description="Category breakdown with percentages")
    recent_transactions_count: int
    total_expense_records: int


class CashflowMethodSummary(BaseModel):
    inflow: float
    outflow: float
    net: float


class CashflowResponse(BaseModel):
    total_inflow: float
    total_outflow: float
    net_cashflow: float
    by_method: Dict[str, CashflowMethodSummary]


class PnLStatementResponse(BaseModel):
    period: str
    gross_rental_revenue: float
    other_income: float
    total_revenue: float
    fleet_maintenance_costs: float
    hub_rent_and_operations: float
    staff_salaries: float
    fuel_and_logistics: float
    insurance_and_compliance: float
    other_expenses: float
    total_operating_expenses: float
    net_operating_income: float
    operating_margin_pct: float

