from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.db.mongodb import get_database

logger = logging.getLogger(__name__)


def _get_db():
    return get_database()


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    item = dict(doc)
    item["id"] = str(item.pop("_id", item.get("id", "")))
    created = item.get("created_at")
    if isinstance(created, datetime):
        item["created_at"] = created.isoformat()
    return item


def create_notification(
    title: str,
    message: str,
    notification_type: str = "vehicle",  # vehicle, booking, payment, maintenance, system
    severity: str = "info",  # info, success, warning, alert
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Insert a persistent notification into the database."""
    db = _get_db()
    if db is None:
        logger.warning("Database unavailable, notification skipped: %s", title)
        return None

    now = datetime.now(timezone.utc)
    t_id = str(tenant_id).strip() if tenant_id else None
    doc = {
        "_id": ObjectId(),
        "title": title.strip(),
        "message": message.strip(),
        "type": notification_type.strip().lower(),
        "severity": severity.strip().lower(),
        "entity_id": str(entity_id) if entity_id else None,
        "entity_type": entity_type.strip().lower() if entity_type else None,
        "tenant_id": t_id,
        "vendor_id": t_id,
        "is_read": False,
        "created_at": now,
        "updated_at": now,
    }

    try:
        db["notifications"].insert_one(doc)
        return _serialize(doc)
    except PyMongoError as exc:
        logger.exception("Failed to insert notification: %s", exc)
        return None


def list_notifications(
    tenant_id: Optional[str] = None,
    unread_only: bool = False,
    notification_type: Optional[str] = None,
    limit: int = 50,
) -> List[dict[str, Any]]:
    """List notifications sorted by newest first."""
    db = _get_db()
    if db is None:
        return []

    query: dict[str, Any] = {}
    if tenant_id:
        query["$or"] = [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]
    else:
        query["tenant_id"] = "__unauthenticated_none__"

    if unread_only:
        query["is_read"] = False

    if notification_type and notification_type.lower() != "all":
        query["type"] = notification_type.lower()

    try:
        cursor = db["notifications"].find(query).sort("created_at", -1).limit(limit)
        return [_serialize(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.exception("Failed to list notifications: %s", exc)
        return []


def mark_notification_as_read(notification_id: str, tenant_id: Optional[str] = None) -> bool:
    """Mark a single notification as read."""
    db = _get_db()
    if db is None:
        return False

    query: dict[str, Any] = {}
    try:
        query["_id"] = ObjectId(notification_id)
    except Exception:
        query["id"] = notification_id

    if tenant_id:
        query["$or"] = [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]

    now = datetime.now(timezone.utc)
    try:
        res = db["notifications"].update_one(query, {"$set": {"is_read": True, "updated_at": now}})
        return res.modified_count > 0 or res.matched_count > 0
    except PyMongoError as exc:
        logger.exception("Failed to mark notification read: %s", exc)
        return False


def mark_all_notifications_as_read(tenant_id: Optional[str] = None) -> int:
    """Mark all unread notifications as read."""
    db = _get_db()
    if db is None:
        return 0

    query: dict[str, Any] = {"is_read": False}
    if tenant_id:
        query["$or"] = [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]
    else:
        query["tenant_id"] = "__unauthenticated_none__"

    now = datetime.now(timezone.utc)
    try:
        res = db["notifications"].update_many(query, {"$set": {"is_read": True, "updated_at": now}})
        return res.modified_count
    except PyMongoError as exc:
        logger.exception("Failed to mark all notifications read: %s", exc)
        return 0


def get_unread_count(tenant_id: Optional[str] = None) -> int:
    """Get the count of unread notifications."""
    db = _get_db()
    if db is None:
        return 0

    query: dict[str, Any] = {"is_read": False}
    if tenant_id:
        query["$or"] = [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]
    else:
        query["tenant_id"] = "__unauthenticated_none__"

    try:
        return db["notifications"].count_documents(query)
    except PyMongoError as exc:
        logger.exception("Failed to count unread notifications: %s", exc)
        return 0


def delete_notification(notification_id: str, tenant_id: Optional[str] = None) -> bool:
    """Delete a notification permanently."""
    db = _get_db()
    if db is None:
        return False

    query: dict[str, Any] = {}
    try:
        query["_id"] = ObjectId(notification_id)
    except Exception:
        query["id"] = notification_id

    if tenant_id:
        query["$or"] = [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]

    try:
        res = db["notifications"].delete_one(query)
        return res.deleted_count > 0
    except PyMongoError as exc:
        logger.exception("Failed to delete notification: %s", exc)
        return False

