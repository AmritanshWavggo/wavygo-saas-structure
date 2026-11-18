from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.modules.auth.security import get_optional_vendor
from app.modules.payments.schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentStatsResponse,
)
from app.modules.payments.service import payment_service

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
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record payment transaction",
    description="Record a cash, UPI, or card payment against a booking, updating both the payment ledger and booking balance.",
)
def record_payment(payload: PaymentCreate, request: Request) -> PaymentResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return payment_service.record_payment(payload, tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to record payment: {str(exc)}",
        )


@router.get(
    "/stats",
    response_model=PaymentStatsResponse,
    summary="Get payment & finance statistics",
    description="Retrieve aggregated metrics for total collected revenue, online/offline split, and outstanding balances.",
)
def get_payment_stats(request: Request) -> PaymentStatsResponse:
    tenant_id = _get_tenant_id(request)
    return payment_service.get_stats(tenant_id=tenant_id)


@router.get(
    "",
    response_model=List[PaymentResponse],
    summary="List payment transactions",
    description="Retrieve all transactions with optional filtering by status (Paid, Partial, Refunded) and keyword search.",
)
def list_payments(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status (Paid, Partial, Refunded)"),
    method: Optional[str] = Query(None, description="Filter by method (UPI, Cash, Card, Bank Transfer)"),
    booking_id: Optional[str] = Query(None, description="Filter by booking ID"),
    query: Optional[str] = Query(None, description="Search by customer name, txn ID, or vehicle"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[PaymentResponse]:
    tenant_id = _get_tenant_id(request)
    return payment_service.list_payments(
        status=status,
        method=method,
        booking_id=booking_id,
        query=query,
        skip=skip,
        limit=limit,
        tenant_id=tenant_id,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get single payment record",
)
def get_payment(payment_id: str, request: Request) -> PaymentResponse:
    tenant_id = _get_tenant_id(request)
    payment = payment_service.get_payment(payment_id, tenant_id=tenant_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment transaction with ID '{payment_id}' not found.",
        )
    return payment


@router.patch(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Update payment record",
    description="Update transaction status (e.g., mark as Refunded) or notes.",
)
def update_payment(payment_id: str, payload: PaymentUpdate, request: Request) -> PaymentResponse:
    tenant_id = _get_tenant_id(request)
    updated = payment_service.update_payment(payment_id, payload, tenant_id=tenant_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found.",
        )
    return updated


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    summary="Refund payment",
)
def refund_payment(payment_id: str, request: Request, reason: Optional[str] = Query(None)) -> PaymentResponse:
    res = payment_service.refund_payment(payment_id, reason=reason)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found.",
        )
    return res
