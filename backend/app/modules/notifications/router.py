
from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import PyMongoError

from app.modules.auth.security import get_current_vendor

router = APIRouter(prefix="/notifications", tags=["notifications"])


def now():
    return datetime.now(timezone.utc)


def get_db(request: Request):
    db = getattr(request.app.state, "database", None)

    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Notification storage is unavailable.",
        )

    return db


def serialize_notification(document: dict[str, Any]):
    document = dict(document)
    document["id"] = str(document.pop("_id"))

    if isinstance(document.get("vendor_id"), ObjectId):
        document["vendor_id"] = str(document["vendor_id"])

    return document


@router.get("/")
def get_notifications(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = False,
):
    db = get_db(request)

    filters = {
        "vendor_id": vendor["_id"],
    }

    if unread_only:
        filters["is_read"] = False

    try:
        notifications = (
            db["notifications"]
            .find(filters)
            .sort("created_at", -1)
            .limit(limit)
        )

        return [
            serialize_notification(notification)
            for notification in notifications
        ]

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve notifications.",
        ) from exc


@router.get("/unread-count")
def get_unread_count(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    db = get_db(request)

    try:
        count = db["notifications"].count_documents({
            "vendor_id": vendor["_id"],
            "is_read": False,
        })

        return {"unread_count": count}

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve unread notification count.",
        ) from exc


@router.patch("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: str,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(404, "Notification not found.")

    db = get_db(request)

    try:
        result = db["notifications"].update_one(
            {
                "_id": ObjectId(notification_id),
                "vendor_id": vendor["_id"],
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": now(),
                }
            },
        )

        if not result.matched_count:
            raise HTTPException(404, "Notification not found.")

        return {"message": "Notification marked as read."}

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not update notification.",
        ) from exc


@router.patch("/mark-all-read")
def mark_all_notifications_as_read(
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    db = get_db(request)

    try:
        result = db["notifications"].update_many(
            {
                "vendor_id": vendor["_id"],
                "is_read": False,
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": now(),
                }
            },
        )

        return {
            "message": "Notifications marked as read.",
            "updated_count": result.modified_count,
        }

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not update notifications.",
        ) from exc


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: str,
    request: Request,
    vendor: Annotated[dict, Depends(get_current_vendor)],
):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(404, "Notification not found.")

    db = get_db(request)

    try:
        result = db["notifications"].delete_one({
            "_id": ObjectId(notification_id),
            "vendor_id": vendor["_id"],
        })

        if not result.deleted_count:
            raise HTTPException(404, "Notification not found.")

        return {"message": "Notification deleted."}

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not delete notification.",
        ) from exc
