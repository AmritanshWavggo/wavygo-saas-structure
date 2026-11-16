from __future__ import annotations

import logging
import re
from datetime import datetime, date, timezone
import time
import uuid
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.db.mongodb import get_database
from app.modules.bookings.schemas import (
    OfflineBookingCreate,
    OfflineBookingUpdate,
    PaymentRecordCreate,
    OfflineBookingResponse,
)

logger = logging.getLogger(__name__)


class BookingService:
    def __init__(self):
        # In-memory store used when MongoDB is not connected (local dev/tests)
        self._memory_bookings: Dict[str, Dict[str, Any]] = {}

    def _get_db(self):
        try:
            return get_database()
        except Exception:
            return None

    @staticmethod
    def _calculate_days(start_str: str, end_str: str) -> int:
        try:
            d1 = date.fromisoformat(start_str)
            d2 = date.fromisoformat(end_str)
            days = (d2 - d1).days
            return max(1, days)
        except Exception:
            return 1

    @staticmethod
    def _format_date_range(start_str: str, end_str: str) -> str:
        try:
            d1 = date.fromisoformat(start_str)
            d2 = date.fromisoformat(end_str)
            s_fmt = d1.strftime("%b %d")
            e_fmt = d2.strftime("%b %d")
            return f"{s_fmt} – {e_fmt}"
        except Exception:
            return f"{start_str} – {end_str}"

    def create_offline_booking(self, payload: OfflineBookingCreate, tenant_id: Optional[str] = None) -> OfflineBookingResponse:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        
        booking_id = f"BK-{int(time.time() * 1000) % 1000000:06d}"
        customer_id = payload.customer.customer_id or f"CU-{int(time.time() * 1000) % 100000:05d}"
        
        rental_days = self._calculate_days(payload.rental.start_date, payload.rental.end_date)
        daily_price = float(payload.vehicle.price_per_day)
        
        base_amount = daily_price * rental_days
        add_on_amount = (500.0 * rental_days) if payload.rental.add_ons else 0.0
        service_fee = round(base_amount * 0.05, 2)
        subtotal = base_amount + add_on_amount + service_fee
        discount_amount = min(subtotal, max(0.0, float(payload.rental.discount)))
        deposit_amount = 2000.0 if payload.payment.deposit else 0.0
        total_amount = subtotal - discount_amount + deposit_amount
        
        initial_paid = min(total_amount, float(payload.payment.paid_amount))
        pending_amount = max(0.0, total_amount - initial_paid)
        
        dates_formatted = self._format_date_range(payload.rental.start_date, payload.rental.end_date)
        
        customer_details = {
            "id": customer_id,
            "name": payload.customer.name.strip(),
            "phone": payload.customer.phone.strip(),
            "email": payload.customer.email.strip() if payload.customer.email else "",
        }
        
        vehicle_details = {
            "id": payload.vehicle.vehicle_id,
            "name": payload.vehicle.vehicle_name,
            "registration": payload.vehicle.registration or "",
            "price_per_day": daily_price,
            "type": payload.vehicle.vehicle_type or "Two-Wheeler",
        }
        
        rental_details = {
            "start_date": payload.rental.start_date,
            "end_date": payload.rental.end_date,
            "pickup_time": payload.rental.pickup_time,
            "return_time": payload.rental.return_time,
            "pickup_location": payload.rental.pickup_location.strip(),
            "add_ons": payload.rental.add_ons,
            "discount": payload.rental.discount,
            "rental_days": rental_days,
        }
        
        payment_details = {
            "method": payload.payment.method,
            "deposit_required": payload.payment.deposit,
            "deposit_amount": deposit_amount,
            "initial_paid": initial_paid,
            "transactions": [
                {
                    "id": f"TX-{uuid.uuid4().hex[:6].upper()}",
                    "amount": initial_paid,
                    "method": payload.payment.method,
                    "date": now_str,
                    "type": "Initial Payment",
                }
            ] if initial_paid > 0 else [],
        }
        
        record: dict[str, Any] = {
            "id": booking_id,
            "customer": payload.customer.name.strip(),
            "vehicle": payload.vehicle.vehicle_name,
            "dates": dates_formatted,
            "type": "Offline",
            "status": "Active",
            "paid": initial_paid,
            "pending": pending_amount,
            "base_amount": base_amount,
            "add_on_amount": add_on_amount,
            "service_fee": service_fee,
            "discount_amount": discount_amount,
            "deposit_amount": deposit_amount,
            "total_amount": total_amount,
            "rental_days": rental_days,
            "vehicle_details": vehicle_details,
            "customer_details": customer_details,
            "rental_details": rental_details,
            "payment_details": payment_details,
            "notes": payload.notes,
            "tenant_id": tenant_id,
            "vendor_id": tenant_id,
            "created_at": now_str,
            "updated_at": now_str,
        }
        
        # Save to Mongo if available, else save to memory store
        db = self._get_db()

        # Mark vehicle as Rented upon booking creation
        v_ident = payload.vehicle.vehicle_id or payload.vehicle.vehicle_name
        if v_ident and db is not None:
            try:
                conds: list[dict[str, Any]] = [{"id": v_ident}, {"_id": v_ident}, {"makeModel": v_ident}, {"name": v_ident}]
                try:
                    if ObjectId.is_valid(v_ident):
                        conds.append({"_id": ObjectId(v_ident)})
                except Exception:
                    pass
                db["vehicles"].update_many(
                    {"$or": conds},
                    {"$set": {"fleetAvailability": "Rented", "availability": "Rented", "updatedAt": now_str}},
                )
            except Exception:
                pass

        # Save to Mongo if available, else save to memory store
        if db is not None:
            try:
                db["bookings"].replace_one(
                    {"id": booking_id},
                    {**record, "_id": booking_id},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Failed to persist booking to Mongo: %s", exc)

            # Auto-sync or create customer in customers module collection
            try:
                phone_raw = payload.customer.phone.strip() if payload.customer.phone else ""
                phone_norm = re.sub(r"\D", "", phone_raw)
                c_name = payload.customer.name.strip()
                c_email = (
                    payload.customer.email.strip().lower()
                    if payload.customer.email and payload.customer.email.strip()
                    else None
                )

                t_id_val = None
                if tenant_id:
                    t_id_val = ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id

                cust_query: dict[str, Any] = {}
                if t_id_val is not None:
                    cust_query["tenant_id"] = t_id_val

                conds: list[dict[str, Any]] = []
                if payload.customer.customer_id:
                    if ObjectId.is_valid(payload.customer.customer_id):
                        conds.append({"_id": ObjectId(payload.customer.customer_id)})
                    else:
                        conds.append({"id": payload.customer.customer_id})
                if phone_norm:
                    conds.append({"phone_normalized": phone_norm})
                if phone_raw:
                    conds.append({"phone": phone_raw})
                if c_email:
                    conds.append({"email": c_email})

                if conds:
                    cust_query["$or"] = conds
                else:
                    cust_query["name"] = c_name

                now_utc = datetime.now(timezone.utc)
                existing_cust = db["customers"].find_one(cust_query)
                if existing_cust:
                    update_ops: dict[str, Any] = {
                        "$inc": {
                            "bookings": 1,
                            "active": 1,
                            "paid": float(initial_paid),
                            "pending": float(pending_amount),
                        },
                        "$set": {
                            "updated_at": now_utc,
                        },
                    }
                    if c_email and not existing_cust.get("email"):
                        update_ops["$set"]["email"] = c_email
                    db["customers"].update_one({"_id": existing_cust["_id"]}, update_ops)
                    customer_details["id"] = str(existing_cust["_id"])
                    record["customer_details"]["id"] = str(existing_cust["_id"])
                else:
                    new_cust: dict[str, Any] = {
                        "name": c_name,
                        "phone": phone_raw,
                        "phone_normalized": phone_norm,
                        "email": c_email,
                        "status": "Verified",
                        "bookings": 1,
                        "active": 1,
                        "paid": float(initial_paid),
                        "pending": float(pending_amount),
                        "created_at": now_utc,
                        "updated_at": now_utc,
                    }
                    if t_id_val is not None:
                        new_cust["tenant_id"] = t_id_val
                    ins_res = db["customers"].insert_one(new_cust)
                    customer_details["id"] = str(ins_res.inserted_id)
                    record["customer_details"]["id"] = str(ins_res.inserted_id)
            except Exception as cust_err:
                logger.warning("Could not auto-sync customer during offline booking: %s", cust_err)

        try:
            from app.modules.notifications.service import create_notification
            b_tenant = tenant_id or getattr(payload, "tenant_id", None)
            create_notification(
                title="Vehicle Rented (New Booking)",
                message=f"{payload.vehicle.vehicle_name} is now Rented for booking {booking_id} by {payload.customer.name}.",
                notification_type="booking",
                severity="success",
                entity_id=booking_id,
                entity_type="booking",
                tenant_id=str(b_tenant) if b_tenant else None,
            )
        except Exception:
            pass
        
        self._memory_bookings[booking_id] = record
        return OfflineBookingResponse.model_validate(record)

    def get_booking(self, booking_id: str, tenant_id: Optional[str] = None) -> Optional[OfflineBookingResponse]:
        db = self._get_db()
        if db is not None:
            try:
                filt: dict[str, Any] = {"$or": [{"id": booking_id}, {"_id": booking_id}]}
                if tenant_id:
                    filt = {
                        "$and": [
                            filt,
                            {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}, {"tenant_id": None}, {"vendor_id": None}]},
                        ]
                    }
                doc = db["bookings"].find_one(filt)
                if doc:
                    doc["id"] = doc.get("id") or str(doc.get("_id"))
                    doc.pop("_id", None)
                    return OfflineBookingResponse.model_validate(doc)
            except Exception as exc:
                logger.error("Failed to get booking from Mongo: %s", exc)

        if booking_id in self._memory_bookings:
            b = self._memory_bookings[booking_id]
            if tenant_id and b.get("tenant_id") and b.get("tenant_id") != tenant_id:
                return None
            return OfflineBookingResponse.model_validate(b)
        return None

    def list_bookings(
        self,
        status: Optional[str] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[OfflineBookingResponse]:
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
                if status and status.lower() != "all":
                    mongo_filter["status"] = status
                if query:
                    regex_q = {"$regex": query, "$options": "i"}
                    query_cond = [
                        {"id": regex_q},
                        {"customer": regex_q},
                        {"vehicle": regex_q},
                    ]
                    if "$or" in mongo_filter:
                        mongo_filter["$and"] = [{"$or": mongo_filter.pop("$or")}, {"$or": query_cond}]
                    else:
                        mongo_filter["$or"] = query_cond
                cursor = db["bookings"].find(mongo_filter).sort("created_at", -1).skip(skip).limit(limit)
                for doc in cursor:
                    doc["id"] = doc.get("id") or str(doc.get("_id"))
                    doc.pop("_id", None)
                    results.append(doc)
            except Exception as exc:
                logger.error("Failed to list bookings from Mongo: %s", exc)

        # Fallback to in-memory store if DB is unreachable or for unauthenticated test suites
        if not results and (db is None or not tenant_id):
            for b in sorted(self._memory_bookings.values(), key=lambda x: x.get("created_at", ""), reverse=True):
                if tenant_id and (b.get("tenant_id") != tenant_id and b.get("vendor_id") != tenant_id):
                    continue
                if status and status.lower() != "all" and b.get("status") != status:
                    continue
                if query:
                    q_lower = query.lower()
                    target = f"{b.get('id', '')} {b.get('customer', '')} {b.get('vehicle', '')}".lower()
                    if q_lower not in target:
                        continue
                results.append(b)
            results = results[skip: skip + limit]

        return [OfflineBookingResponse.model_validate(item) for item in results]

    def update_booking(self, booking_id: str, payload: OfflineBookingUpdate, tenant_id: Optional[str] = None) -> Optional[OfflineBookingResponse]:
        booking = self.get_booking(booking_id, tenant_id=tenant_id)
        if not booking:
            return None

        update_dict: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.status:
            update_dict["status"] = payload.status
        if payload.pickup_location:
            update_dict["rental_details.pickup_location"] = payload.pickup_location
        if payload.notes is not None:
            update_dict["notes"] = payload.notes

        # Update in Mongo
        db = self._get_db()
        if db is not None:
            try:
                db["bookings"].update_one(
                    {"$or": [{"id": booking_id}, {"_id": booking_id}]},
                    {"$set": update_dict},
                )
            except Exception as exc:
                logger.error("Failed to update booking in Mongo: %s", exc)

        # When booking completes (bike returned), vehicle goes to 'Under Review' for mechanic inspection
        if payload.status == "Completed":
            v_id = booking.vehicle_details.get("id") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "id", None)
            v_reg = booking.vehicle_details.get("registration") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "registration", None)
            v_ident = v_id or booking.vehicle
            if (v_ident or v_reg) and db is not None:
                try:
                    conds: list[dict[str, Any]] = []
                    if v_ident:
                        s_id = str(v_ident).strip()
                        conds.extend([
                            {"id": s_id},
                            {"_id": s_id},
                            {"makeModel": s_id},
                            {"name": s_id},
                            {"registration": s_id},
                            {"registrationNumber": s_id},
                        ])
                        if ObjectId.is_valid(s_id):
                            conds.append({"_id": ObjectId(s_id)})
                    if v_reg:
                        s_reg = str(v_reg).strip()
                        conds.extend([
                            {"registration": s_reg},
                            {"registrationNumber": s_reg},
                        ])
                    if conds:
                        db["vehicles"].update_many(
                            {"$or": conds},
                            {"$set": {"fleetAvailability": "Under Review", "availability": "Under Review", "updatedAt": update_dict["updated_at"]}},
                        )
                except Exception:
                    pass
            try:
                from app.modules.notifications.service import create_notification
                b_tenant = tenant_id or getattr(booking, "tenant_id", None) or getattr(booking, "vendor_id", None)
                create_notification(
                    title="Rental Completed",
                    message=f"Booking {booking_id} completed. Vehicle {booking.vehicle} moved to Under Review for inspection.",
                    notification_type="booking",
                    severity="info",
                    entity_id=booking_id,
                    entity_type="booking",
                    tenant_id=str(b_tenant) if b_tenant else None,
                )
            except Exception:
                pass

        # Update customer active count if booking ended
        if payload.status in ("Completed", "Cancelled") and db is not None:
            try:
                c_id = (
                    booking.customer_details.get("id")
                    if isinstance(booking.customer_details, dict)
                    else getattr(booking.customer_details, "id", None)
                ) if booking.customer_details else None
                c_cond: dict[str, Any] = {}
                if c_id and ObjectId.is_valid(c_id):
                    c_cond["_id"] = ObjectId(c_id)
                elif booking.customer:
                    c_cond["name"] = booking.customer
                if c_cond:
                    db["customers"].update_one(
                        c_cond,
                        {
                            "$inc": {"active": -1},
                            "$set": {"updated_at": datetime.now(timezone.utc)},
                        },
                    )
            except Exception:
                pass
        # Update in memory
        if booking_id in self._memory_bookings:
            mem = self._memory_bookings[booking_id]
            if payload.status:
                mem["status"] = payload.status
            if payload.pickup_location:
                if "rental_details" not in mem or not isinstance(mem["rental_details"], dict):
                    mem["rental_details"] = {}
                mem["rental_details"]["pickup_location"] = payload.pickup_location
            if payload.notes is not None:
                mem["notes"] = payload.notes
            mem["updated_at"] = update_dict["updated_at"]

        return self.get_booking(booking_id)

    def record_payment(self, booking_id: str, payment: PaymentRecordCreate, tenant_id: Optional[str] = None) -> Optional[OfflineBookingResponse]:
        booking = self.get_booking(booking_id, tenant_id=tenant_id)
        if not booking:
            return None

        new_paid = booking.paid + payment.amount
        new_pending = max(0.0, booking.total_amount - new_paid)
        now_str = datetime.now(timezone.utc).isoformat()

        tx = {
            "id": f"TX-{uuid.uuid4().hex[:6].upper()}",
            "amount": payment.amount,
            "method": payment.method,
            "notes": payment.notes,
            "date": now_str,
            "type": "Partial / Full Payment",
        }

        # Update in Mongo first
        db = self._get_db()
        if db is not None:
            try:
                db["bookings"].update_one(
                    {"$or": [{"id": booking_id}, {"_id": booking_id}]},
                    {
                        "$set": {"paid": new_paid, "pending": new_pending, "updated_at": now_str},
                        "$push": {"payment_details.transactions": tx},
                    },
                )
            except Exception as exc:
                logger.error("Failed to update booking in Mongo: %s", exc)

        # Update customer paid and pending metrics in Mongo
        if db is not None:
            try:
                c_id = (
                    booking.customer_details.get("id")
                    if isinstance(booking.customer_details, dict)
                    else getattr(booking.customer_details, "id", None)
                ) if booking.customer_details else None
                c_cond: dict[str, Any] = {}
                if c_id and ObjectId.is_valid(c_id):
                    c_cond["_id"] = ObjectId(c_id)
                elif booking.customer:
                    c_cond["name"] = booking.customer
                if c_cond:
                    db["customers"].update_one(
                        c_cond,
                        {
                            "$inc": {"paid": float(payment.amount), "pending": -float(payment.amount)},
                            "$set": {"updated_at": datetime.now(timezone.utc)},
                        },
                    )
            except Exception:
                pass
        if booking_id in self._memory_bookings:
            mem = self._memory_bookings[booking_id]
            mem["paid"] = new_paid
            mem["pending"] = new_pending
            mem["updated_at"] = now_str
            if "payment_details" not in mem:
                mem["payment_details"] = {}
            if "transactions" not in mem["payment_details"]:
                mem["payment_details"]["transactions"] = []
            mem["payment_details"]["transactions"].append(tx)

        try:
            from app.modules.notifications.service import create_notification
            b_tenant = tenant_id or getattr(booking, "tenant_id", None) or getattr(booking, "vendor_id", None)
            create_notification(
                title="Payment Received",
                message=f"Payment of ₹{payment.amount} recorded for booking {booking_id} via {payment.method}.",
                notification_type="payment",
                severity="success",
                entity_id=booking_id,
                entity_type="booking",
                tenant_id=str(b_tenant) if b_tenant else None,
            )
        except Exception:
            pass

        return self.get_booking(booking_id)


booking_service = BookingService()
