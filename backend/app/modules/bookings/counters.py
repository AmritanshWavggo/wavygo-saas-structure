"""
Atomic sequence counter generator for human-readable booking numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument


def generate_booking_number(db, tenant_id: ObjectId, year: int | None = None) -> str:
    """
    Generate an atomic, sequential booking number scoped per tenant and calendar year.
    Example: 'BK-2026-0001'.
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    sequence_key = f"bookings-{year}"
    counter = db["counters"].find_one_and_update(
        {"tenantId": tenant_id, "sequence": sequence_key},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    val = counter.get("value", 1)
    return f"BK-{year}-{val:04d}"

