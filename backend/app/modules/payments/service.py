from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
import uuid
import secrets
from typing import Optional, List, Dict, Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.db.mongodb import get_database
from app.modules.payments.schemas import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentStatsResponse

logger = logging.getLogger(__name__)


def inr_to_paise(val: float) -> int:
    return int(round(float(val) * 100))


def paise_to_inr(paise: int) -> float:
    return round(float(paise) / 100.0, 2)


class PaymentService:
    def __init__(self):
        # In-memory store fallback for unauthenticated demo mode only
        self._memory_payments: Dict[str, Dict[str, Any]] = {}
        self._seed_default_payments()

    def _get_db(self):
        try:
            return get_database()
        except Exception:
            return None

    def _seed_default_payments(self):
        initial = [
            {
                "id": "TX-7082",
                "booking": "BK-3984",
                "customer": "Aarav Mehta",
                "method": "UPI",
                "date": "Oct 12, 2026",
                "amount": 3798.0,
                "status": "Paid",
                "notes": "Full advance via UPI",
                "transaction_reference": "UPI/428910385920",
                "idempotency_key": "seed-tx-7082",
                "created_at": "2026-10-12T10:30:00",
                "updated_at": "2026-10-12T10:30:00",
            },
            {
                "id": "TX-7081",
                "booking": "BK-3983",
                "customer": "Isha Patel",
                "method": "Cash",
                "date": "Oct 12, 2026",
                "amount": 649.0,
                "status": "Partial",
                "notes": "Counter advance cash",
                "transaction_reference": "CASH/STORE-1",
                "idempotency_key": "seed-tx-7081",
                "created_at": "2026-10-12T11:15:00",
                "updated_at": "2026-10-12T11:15:00",
            },
            {
                "id": "TX-7080",
                "booking": "BK-3982",
                "customer": "Rohan Shah",
                "method": "Card",
                "date": "Oct 11, 2026",
                "amount": 2398.0,
                "status": "Paid",
                "notes": "POS terminal swipe",
                "transaction_reference": "CARD/****4092",
                "idempotency_key": "seed-tx-7080",
                "created_at": "2026-10-11T14:20:00",
                "updated_at": "2026-10-11T14:20:00",
            },
            {
                "id": "TX-7079",
                "booking": "BK-3981",
                "customer": "Ananya Desai",
                "method": "UPI",
                "date": "Oct 11, 2026",
                "amount": 2198.0,
                "status": "Partial",
                "notes": "Online UPI QR payment",
                "transaction_reference": "UPI/428719401829",
                "idempotency_key": "seed-tx-7079",
                "created_at": "2026-10-11T16:45:00",
                "updated_at": "2026-10-11T16:45:00",
            },
            {
                "id": "TX-7078",
                "booking": "BK-3980",
                "customer": "Kabir Joshi",
                "method": "UPI",
                "date": "Oct 10, 2026",
                "amount": 599.0,
                "status": "Paid",
                "notes": "Fast UPI checkout",
                "transaction_reference": "UPI/428519028471",
                "idempotency_key": "seed-tx-7078",
                "created_at": "2026-10-10T09:10:00",
                "updated_at": "2026-10-10T09:10:00",
            },
        ]
        for item in initial:
            self._memory_payments[item["id"]] = item

    def _generate_tx_id(self) -> str:
        # Cryptographically strong, high-entropy unique identifier
        ts = int(time.time() * 1000) % 1000000
        rand_suffix = secrets.token_hex(3).upper()
        return f"TX-{ts:06d}-{rand_suffix}"

    def record_payment_with_replay(self, payload: PaymentCreate, tenant_id: Optional[str] = None) -> tuple[PaymentResponse, bool]:
        """
        Records a booking payment and returns (PaymentResponse, is_replay: bool).
        """
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to record payments.",
            )

        db = self._get_db()
        if db is None:
            # Rule: For an authenticated tenant, if Mongo is unavailable return 503. Never write to in-memory store.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable. Cannot record payment.",
            )

        tenant_id_str = str(tenant_id)

        # 1. Check Idempotency Key
        idemp_key = payload.idempotency_key.strip()
        existing_payment = db["payments"].find_one({
            "$and": [
                {"$or": [{"tenant_id": tenant_id_str}, {"vendor_id": tenant_id_str}]},
                {"idempotency_key": idemp_key},
            ]
        })

        if existing_payment:
            # Check if payload matches original request
            matches_booking = existing_payment.get("booking") == payload.booking_id.strip()
            matches_amount = inr_to_paise(existing_payment.get("amount", 0.0)) == inr_to_paise(payload.amount)
            matches_method = (existing_payment.get("method") or "").strip().lower() == payload.method.strip().lower()
            existing_ref = existing_payment.get("transaction_reference") or None
            payload_ref = payload.transaction_reference or None
            matches_ref = existing_ref == payload_ref

            if matches_booking and matches_amount and matches_method and matches_ref:
                # Return the original payment with 200 (idempotent replay)
                existing_payment.pop("_id", None)
                return PaymentResponse(**existing_payment), True
            else:
                # Same key with different payload -> 409 Conflict
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key already used with a different payment payload.",
                )

        # 2. Scoped Booking Lookup
        b_filter: dict[str, Any] = {
            "$and": [
                {"$or": [{"id": payload.booking_id.strip()}, {"_id": payload.booking_id.strip()}]},
                {"$or": [
                    {"tenant_id": tenant_id_str},
                    {"tenant_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id_str},
                    {"vendor_id": tenant_id_str},
                    {"vendor_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id_str},
                ]},
            ]
        }
        booking = db["bookings"].find_one(b_filter)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking '{payload.booking_id}' not found.",
            )

        # 3. Reject Cancelled Bookings
        if booking.get("status") == "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot record payment for a cancelled booking.",
            )

        # 4. Money & Outstanding Calculation in Paise
        total_paise = inr_to_paise(booking.get("total_amount", 0.0))
        current_paid_paise = inr_to_paise(booking.get("paid", 0.0))
        payment_amount_paise = inr_to_paise(payload.amount)
        outstanding_paise = max(0, total_paise - current_paid_paise)

        if payment_amount_paise > outstanding_paise:
            outstanding_inr = paise_to_inr(outstanding_paise)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment amount of ₹{payload.amount:.2f} exceeds outstanding balance of ₹{outstanding_inr:.2f}.",
            )

        # 5. Duplicate Transaction Reference on the SAME Booking
        if payload.transaction_reference:
            clean_ref = payload.transaction_reference.strip()
            dup_ref = db["payments"].find_one({
                "$and": [
                    {"$or": [{"tenant_id": tenant_id_str}, {"vendor_id": tenant_id_str}]},
                    {"booking": payload.booking_id.strip()},
                    {"transaction_reference": clean_ref},
                ]
            })
            if dup_ref:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Transaction reference '{clean_ref}' has already been recorded for this booking.",
                )

        # 6. Prepare Record Data
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        date_formatted = payload.payment_date or now_dt.strftime("%b %d, %Y")
        tx_id = self._generate_tx_id()
        customer_name = payload.customer_name or booking.get("customer") or "Walk-in Customer"

        # Booking totals are stored as INR floats.  Normalize the increment through
        # paise so every write is a two-decimal amount; the database update below
        # must still use $inc so it is based on the current document, not this read.
        payment_amount_inr = paise_to_inr(payment_amount_paise)

        tx_entry = {
            "id": tx_id,
            "amount": payment_amount_inr,
            "method": payload.method.strip(),
            "notes": payload.notes.strip() if payload.notes else None,
            "transaction_reference": payload.transaction_reference.strip() if payload.transaction_reference else None,
            "date": now_str,
            "type": "Partial / Full Payment",
        }

        # 7. Atomic Execution & Compensation
        # Conditional update on booking with $expr ensuring paid + amount <= total_amount
        conditional_filter = {
            "$and": [
                {"$or": [{"id": payload.booking_id.strip()}, {"_id": payload.booking_id.strip()}]},
                {"$or": [
                    {"tenant_id": tenant_id_str},
                    {"tenant_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id_str},
                    {"vendor_id": tenant_id_str},
                    {"vendor_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id_str},
                ]},
                {"status": {"$ne": "Cancelled"}},
                {
                    "$expr": {
                        "$lte": [
                            {"$add": [{"$ifNull": ["$paid", 0.0]}, payment_amount_inr]},
                            {"$add": [{"$ifNull": ["$total_amount", 0.0]}, 0.001]},  # Small float tolerance
                        ]
                    }
                },
            ]
        }

        updated_booking = db["bookings"].find_one_and_update(
            conditional_filter,
            {
                "$inc": {
                    "paid": payment_amount_inr,
                    "pending": -payment_amount_inr,
                },
                "$set": {"updated_at": now_str},
                "$push": {"payment_details.transactions": tx_entry},
            },
            return_document=True,
        )

        if not updated_booking:
            # Check why conditional update failed
            fresh_booking = db["bookings"].find_one(b_filter)
            if not fresh_booking:
                raise HTTPException(status_code=404, detail="Booking not found.")
            if fresh_booking.get("status") == "Cancelled":
                raise HTTPException(status_code=409, detail="Cannot record payment for a cancelled booking.")
            fresh_paid = fresh_booking.get("paid", 0.0)
            fresh_total = fresh_booking.get("total_amount", 0.0)
            fresh_outstanding = max(0.0, fresh_total - fresh_paid)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment rejected: amount of ₹{payload.amount:.2f} exceeds outstanding balance of ₹{fresh_outstanding:.2f}.",
            )

        # Build payment document
        payment_record: Dict[str, Any] = {
            "id": tx_id,
            "_id": tx_id,
            "booking": payload.booking_id.strip(),
            "customer": customer_name.strip(),
            "method": payload.method.strip(),
            "date": date_formatted,
            "amount": payment_amount_inr,
            "status": "Paid" if inr_to_paise(updated_booking.get("pending", 0.0)) == 0 else "Partial",
            "notes": payload.notes.strip() if payload.notes else None,
            "transaction_reference": payload.transaction_reference.strip() if payload.transaction_reference else None,
            "idempotency_key": idemp_key,
            "payment_date": payload.payment_date,
            "tenant_id": tenant_id_str,
            "vendor_id": tenant_id_str,
            "created_at": now_str,
            "updated_at": now_str,
        }

        try:
            db["payments"].insert_one(payment_record)
        except DuplicateKeyError as exc:
            # Compensation: rollback booking update immediately
            db["bookings"].update_one(
                {"_id": updated_booking["_id"]},
                {
                    "$inc": {"paid": -payment_amount_inr, "pending": payment_amount_inr},
                    "$set": {"updated_at": now_str},
                    "$pull": {"payment_details.transactions": {"id": tx_id}},
                },
            )
            logger.warning("Duplicate key during payment insert: %s", exc)
            # Check if idempotency key collided concurrently
            existing_collision = db["payments"].find_one({
                "$and": [
                    {"$or": [{"tenant_id": tenant_id_str}, {"vendor_id": tenant_id_str}]},
                    {"idempotency_key": idemp_key},
                ]
            })
            if existing_collision:
                existing_collision.pop("_id", None)
                return PaymentResponse(**existing_collision), True
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction reference or idempotency key collision.",
            )
        except PyMongoError as exc:
            # Compensation: rollback booking update
            db["bookings"].update_one(
                {"_id": updated_booking["_id"]},
                {
                    "$inc": {"paid": -payment_amount_inr, "pending": payment_amount_inr},
                    "$set": {"updated_at": now_str},
                    "$pull": {"payment_details.transactions": {"id": tx_id}},
                },
            )
            logger.error("Failed to insert payment record: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to record payment in database.",
            )

        # 8. Safely Update Customer Paid / Pending Counters Once
        try:
            c_id = (
                booking.get("customer_details", {}).get("id")
                if isinstance(booking.get("customer_details"), dict)
                else None
            )
            c_cond: dict[str, Any] = {}
            if c_id and ObjectId.is_valid(c_id):
                c_cond = {"_id": ObjectId(c_id)}
            elif booking.get("customer"):
                c_cond = {
                    "name": booking.get("customer"),
                    "$or": [
                        {"tenant_id": tenant_id_str},
                        {"tenant_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id_str},
                    ],
                }
            if c_cond:
                db["customers"].update_one(
                    c_cond,
                    {
                        "$inc": {"paid": float(payload.amount), "pending": -float(payload.amount)},
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                    },
                )
        except Exception as exc:
            logger.debug("Non-fatal customer counter sync: %s", exc)

        # 9. Create Notification
        try:
            from app.modules.notifications.service import create_notification
            create_notification(
                title="Payment Received",
                message=f"Payment of ₹{payload.amount:.2f} recorded for booking {payload.booking_id} via {payload.method}.",
                notification_type="payment",
                severity="success",
                entity_id=payload.booking_id,
                entity_type="booking",
                tenant_id=tenant_id_str,
            )
        except Exception:
            pass

        payment_record.pop("_id", None)
        return PaymentResponse(**payment_record), False

    def record_payment(self, payload: PaymentCreate, tenant_id: Optional[str] = None) -> PaymentResponse:
        """Centralized payment recording returning PaymentResponse directly."""
        res, _ = self.record_payment_with_replay(payload, tenant_id=tenant_id)
        return res

    def list_payments(
        self,
        status: Optional[str] = None,
        method: Optional[str] = None,
        booking_id: Optional[str] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[PaymentResponse]:
        results: List[Dict[str, Any]] = []

        db = self._get_db()
        if db is not None:
            try:
                mongo_filter: Dict[str, Any] = {}
                if tenant_id:
                    mongo_filter["$or"] = [
                        {"tenant_id": str(tenant_id)},
                        {"vendor_id": str(tenant_id)},
                    ]
                else:
                    mongo_filter["tenant_id"] = "__unauthenticated_none__"
                if booking_id:
                    mongo_filter["booking"] = booking_id
                if status and status.lower() != "all":
                    mongo_filter["status"] = status
                if method and method.lower() != "all":
                    mongo_filter["method"] = method
                if query:
                    regex_q = {"$regex": query, "$options": "i"}
                    query_cond = [
                        {"id": regex_q},
                        {"booking": regex_q},
                        {"customer": regex_q},
                        {"method": regex_q},
                        {"transaction_reference": regex_q},
                    ]
                    if "$or" in mongo_filter:
                        mongo_filter["$and"] = [{"$or": mongo_filter.pop("$or")}, {"$or": query_cond}]
                    else:
                        mongo_filter["$or"] = query_cond

                cursor = db["payments"].find(mongo_filter).sort("created_at", -1).skip(skip).limit(limit)
                for doc in cursor:
                    doc.pop("_id", None)
                    results.append(doc)
            except Exception as exc:
                logger.error("Error listing payments from Mongo: %s", exc)

        # Fallback to in-memory store ONLY for unauthenticated demo requests
        if not results and (db is None or not tenant_id):
            if not tenant_id:
                for p in sorted(self._memory_payments.values(), key=lambda x: x.get("created_at", ""), reverse=True):
                    if booking_id and p.get("booking") != booking_id:
                        continue
                    if status and status.lower() != "all" and p.get("status", "").lower() != status.lower():
                        continue
                    if method and method.lower() != "all" and p.get("method", "").lower() != method.lower():
                        continue
                    if query:
                        q_lower = query.lower()
                        target = f"{p.get('id', '')} {p.get('booking', '')} {p.get('customer', '')} {p.get('method', '')} {p.get('transaction_reference', '')}".lower()
                        if q_lower not in target:
                            continue
                    results.append(p)
                results = results[skip: skip + limit]

        return [PaymentResponse(**item) for item in results]

    def get_payment(self, payment_id: str, tenant_id: Optional[str] = None) -> Optional[PaymentResponse]:
        db = self._get_db()
        if db is not None:
            try:
                filt: dict[str, Any] = {"$or": [{"id": payment_id}, {"_id": payment_id}]}
                if tenant_id:
                    filt = {
                        "$and": [
                            filt,
                            {"$or": [
                                {"tenant_id": str(tenant_id)},
                                {"vendor_id": str(tenant_id)},
                                {"tenant_id": None},
                                {"vendor_id": None},
                            ]},
                        ]
                    }
                doc = db["payments"].find_one(filt)
                if doc:
                    doc.pop("_id", None)
                    return PaymentResponse(**doc)
            except Exception:
                pass

        if not tenant_id and payment_id in self._memory_payments:
            p = self._memory_payments[payment_id]
            return PaymentResponse(**p)
        return None

    def update_payment(self, payment_id: str, payload: PaymentUpdate, tenant_id: Optional[str] = None) -> Optional[PaymentResponse]:
        existing = self.get_payment(payment_id, tenant_id=tenant_id)
        if not existing:
            return None

        update_dict: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.status is not None:
            update_dict["status"] = payload.status
        if payload.notes is not None:
            update_dict["notes"] = payload.notes

        db = self._get_db()
        if db is not None:
            try:
                filt: dict[str, Any] = {"$or": [{"id": payment_id}, {"_id": payment_id}]}
                if tenant_id:
                    filt = {
                        "$and": [
                            filt,
                            {"$or": [{"tenant_id": str(tenant_id)}, {"vendor_id": str(tenant_id)}]},
                        ]
                    }
                db["payments"].update_one(filt, {"$set": update_dict})
            except Exception:
                pass

        if not tenant_id and payment_id in self._memory_payments:
            self._memory_payments[payment_id].update(update_dict)

        return self.get_payment(payment_id, tenant_id=tenant_id) or PaymentResponse(**{**existing.dict(), **update_dict})

    def refund_payment(self, payment_id: str, reason: Optional[str] = None, tenant_id: Optional[str] = None) -> Optional[PaymentResponse]:
        notes = f"Refunded: {reason}" if reason else "Refund processed"
        return self.update_payment(payment_id, PaymentUpdate(status="Refunded", notes=notes), tenant_id=tenant_id)

    def get_stats(self, tenant_id: Optional[str] = None) -> PaymentStatsResponse:
        all_payments = self.list_payments(limit=1000, tenant_id=tenant_id)
        collected_statuses = {"Paid", "Partial"}
        collected = [p for p in all_payments if p.status in collected_statuses]
        total_collected = round(sum(p.amount for p in collected), 2)
        online_collected = round(sum(p.amount for p in collected if p.method in ["UPI", "Card", "Net Banking"]), 2)
        offline_collected = round(sum(p.amount for p in collected if p.method in ["Cash", "Bank Transfer"]), 2)

        # Calculate pending balances from non-cancelled bookings
        pending_balance = 0.0
        db = self._get_db()
        if db is not None and tenant_id:
            try:
                t_str = str(tenant_id)
                pipeline = [
                    {
                        "$match": {
                            "$and": [
                                {"$or": [
                                    {"tenant_id": t_str},
                                    {"tenant_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else t_str},
                                    {"vendor_id": t_str},
                                    {"vendor_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else t_str},
                                ]},
                                {"status": {"$ne": "Cancelled"}},
                            ]
                        }
                    },
                    {
                        "$project": {
                            "pending": {
                                "$max": [
                                    0.0,
                                    {"$subtract": [{"$ifNull": ["$total_amount", 0.0]}, {"$ifNull": ["$paid", 0.0]}]},
                                ]
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "total_pending": {"$sum": "$pending"},
                        }
                    },
                ]
                agg_res = list(db["bookings"].aggregate(pipeline))
                if agg_res:
                    pending_balance = round(float(agg_res[0].get("total_pending", 0.0)), 2)
            except Exception as exc:
                logger.error("Failed to compute pending balance from DB: %s", exc)
        elif not tenant_id:
            # Demo fallback
            try:
                from app.modules.bookings.service import booking_service
                bookings = booking_service.list_bookings(limit=500, tenant_id=tenant_id)
                pending_balance = sum(b.pending for b in bookings)
            except Exception:
                pending_balance = 0.0

        return PaymentStatsResponse(
            total_collected=total_collected,
            online_collected=online_collected,
            offline_collected=offline_collected,
            pending_balance=pending_balance,
            total_transactions=len(all_payments),
        )


payment_service = PaymentService()
