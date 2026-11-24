from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.modules.auth.security import get_optional_vendor
from app.modules.finance.schemas import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    FinanceOverviewResponse,
    CashflowResponse,
    PnLStatementResponse,
)
from app.modules.finance.service import finance_service

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


@router.get(
    "/overview",
    response_model=FinanceOverviewResponse,
    summary="Get overall finance summary & metrics",
    description="Returns verified collected revenue, online/offline breakdown, operating expenses, maintenance costs, net profit, comparison chart, and expense breakdown.",
)
def get_finance_overview(request: Request) -> FinanceOverviewResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return finance_service.get_overview(tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate finance overview: {str(exc)}",
        )


@router.get(
    "/cashflow",
    response_model=CashflowResponse,
    summary="Get cash flow statement",
    description="Returns aggregate cash inflows, outflows, and net cashflow broken down by payment method (UPI, Cash, Bank Transfer, Card).",
)
def get_cashflow(request: Request) -> CashflowResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return finance_service.get_cashflow(tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cashflow statement: {str(exc)}",
        )


@router.get(
    "/pnl",
    response_model=PnLStatementResponse,
    summary="Get Profit & Loss (P&L) statement",
    description="Returns gross rental income, operational breakdown (rent, salaries, fuel, maintenance, insurance), net income, and operating margin.",
)
def get_pnl(request: Request) -> PnLStatementResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return finance_service.get_pnl(tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate P&L statement: {str(exc)}",
        )


@router.post(
    "/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create expense entry",
    description="Add an operational or facility expense record (Rent, Salary, Fuel, Parts, Marketing, etc.).",
)
def create_expense(payload: ExpenseCreate, request: Request) -> ExpenseResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return finance_service.create_expense(payload, tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create expense: {str(exc)}",
        )


@router.get(
    "/expenses",
    response_model=List[ExpenseResponse],
    summary="List expenses",
    description="Retrieve all operational expenses with optional filtering by category, status, and search query.",
)
def list_expenses(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category (Rent & Operations, Staff Salaries, Maintenance, Fuel, Utilities, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (Paid, Pending)"),
    query: Optional[str] = Query(None, description="Search by title, payee, or reference"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[ExpenseResponse]:
    tenant_id = _get_tenant_id(request)
    return finance_service.list_expenses(
        category=category,
        status=status,
        query=query,
        skip=skip,
        limit=limit,
        tenant_id=tenant_id,
    )


@router.get(
    "/expenses/{expense_id}",
    response_model=ExpenseResponse,
    summary="Get expense details",
)
def get_expense(expense_id: str, request: Request) -> ExpenseResponse:
    expense = finance_service.get_expense(expense_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID '{expense_id}' not found.",
        )
    return expense


@router.patch(
    "/expenses/{expense_id}",
    response_model=ExpenseResponse,
    summary="Update expense",
)
def update_expense(expense_id: str, payload: ExpenseUpdate, request: Request) -> ExpenseResponse:
    updated = finance_service.update_expense(expense_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID '{expense_id}' not found.",
        )
    return updated


@router.delete(
    "/expenses/{expense_id}",
    summary="Delete expense",
)
def delete_expense(expense_id: str, request: Request) -> dict:
    success = finance_service.delete_expense(expense_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID '{expense_id}' not found.",
        )
    return {"success": True, "message": f"Expense {expense_id} deleted successfully."}
