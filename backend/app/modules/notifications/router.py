from __future__ import annotations

from typing import Annotated, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.modules.auth.security import get_optional_vendor
from app.modules.notifications import service

router = APIRouter()


class CreateNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    message: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="vehicle")
    severity: str = Field(default="info")
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None


@router.get("", response_model=List[dict[str, Any]], summary="List notifications")
@router.get("/", response_model=List[dict[str, Any]], include_in_schema=False)
def list_notifications(
    unread_only: bool = Query(default=False),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> List[dict[str, Any]]:
    tenant_id = str(vendor["_id"]) if vendor else None
    return service.list_notifications(tenant_id=tenant_id, unread_only=unread_only, notification_type=type, limit=limit)


@router.get("/unread-count", summary="Get unread notification count")
def get_unread_count(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, int]:
    tenant_id = str(vendor["_id"]) if vendor else None
    count = service.get_unread_count(tenant_id=tenant_id)
    return {"unread_count": count}


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create notification")
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_notification(
    payload: CreateNotificationRequest,
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, Any]:
    tenant_id = str(vendor["_id"]) if vendor else None
    item = service.create_notification(
        title=payload.title,
        message=payload.message,
        notification_type=payload.type,
        severity=payload.severity,
        entity_id=payload.entity_id,
        entity_type=payload.entity_type,
        tenant_id=tenant_id,
    )
    if not item:
        raise HTTPException(status_code=500, detail="Failed to create notification.")
    return item


@router.patch("/{notification_id}/read", summary="Mark notification as read")
def mark_read(
    notification_id: str,
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, Any]:
    tenant_id = str(vendor["_id"]) if vendor else None
    success = service.mark_notification_as_read(notification_id, tenant_id=tenant_id)
    return {"success": success, "id": notification_id}


@router.post("/mark-all-read", summary="Mark all notifications as read")
def mark_all_read(
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, Any]:
    tenant_id = str(vendor["_id"]) if vendor else None
    count = service.mark_all_notifications_as_read(tenant_id=tenant_id)
    return {"success": True, "marked_count": count}


@router.delete("/{notification_id}", summary="Delete notification")
def delete_notification(
    notification_id: str,
    vendor: Annotated[Optional[dict[str, Any]], Depends(get_optional_vendor)] = None,
) -> dict[str, Any]:
    tenant_id = str(vendor["_id"]) if vendor else None
    success = service.delete_notification(notification_id, tenant_id=tenant_id)
    return {"success": success, "id": notification_id}
