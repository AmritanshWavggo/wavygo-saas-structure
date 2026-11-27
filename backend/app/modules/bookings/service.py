from __future__ import annotations

import logging
import re
from datetime import datetime, date, time as datetime_time, timezone, timedelta
import time
import uuid
from typing import Optional, List, Dict, Any
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.db.mongodb import create_mongo_client, get_database, mongo_transaction
from app.modules.bookings.schemas import (
    OfflineBookingCreate,
    OfflineBookingUpdate,
    PaymentRecordCreate,
    LifecycleActionRequest,
    ReturnBookingRequest,
    OfflineBookingResponse,
)

logger = logging.getLogger(__name__)

LATE_GRACE_MINUTES = 0


class BookingService:
    def __init__(self):
        # In-memory store used when MongoDB is not connected (local dev/tests)
        self._memory_bookings: Dict[str, Dict[str, Any]] = {}

    def _get_db(self):
        try:
            return get_database()
        except Exception:
            return None

    def _get_client(self):
        try:
            return create_mongo_client()
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

    @staticmethod
    def _round_money(amount: float) -> float:
        return round(float(amount) + 1e-9, 2)

    @staticmethod
    def _enrich_booking_payment_fields(doc: dict[str, Any]) -> dict[str, Any]:
        total = float(doc.get("total_amount", 0.0))
        paid = float(doc.get("paid", 0.0))
        total_paise = int(round(total * 100))
        paid_paise = int(round(paid * 100))
        outstanding_paise = max(0, total_paise - paid_paise)
        outstanding = round(outstanding_paise / 100.0, 2)

        if paid_paise == 0:
            p_status = "Unpaid"
        elif paid_paise < total_paise:
            p_status = "Partially Paid"
        else:
            p_status = "Paid"

        doc["outstanding"] = outstanding
        doc["payment_status"] = p_status
        doc["pending"] = outstanding
        return doc

    # FIX: Check if rental dates overlap with open maintenance schedule
    @staticmethod
    def _dates_overlap(start: str, end: str, other_start: str, other_end: str) -> bool:
        """Return whether two inclusive ISO-date ranges overlap."""
        try:
            return max(date.fromisoformat(start), date.fromisoformat(other_start)) <= min(
                date.fromisoformat(end), date.fromisoformat(other_end)
            )
        except (TypeError, ValueError):
            # A malformed open-maintenance date must not make the vehicle bookable.
            return True

    # FIX: Single booking-admission guard: reject booking if vehicle is under maintenance or overlaps open maintenance
    def assert_vehicle_bookable(
        self,
        vehicle_id: str,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str],
        vehicle_name: Optional[str] = None,
    ) -> None:
        """Raise 409 when a vehicle is in, or overlaps, open maintenance.

        This is deliberately the single booking-admission check so every booking
        creation path uses the same maintenance rule.
        """
        db = self._get_db()
        if db is None:
            return

        vehicle_conditions = [{"id": vehicle_id}, {"_id": vehicle_id}]
        if vehicle_name:
            vehicle_conditions.extend([{"makeModel": vehicle_name}, {"name": vehicle_name}])
        tenant_conditions = [{"tenantId": tenant_id}, {"tenant_id": tenant_id}, {"vendor_id": tenant_id}]
        vehicle = db["vehicles"].find_one({"$and": [{"$or": vehicle_conditions}, {"$or": tenant_conditions}]})
        # FIX: Reject vehicles whose operational availability is Maintenance
        if vehicle and (vehicle.get("availability") == "Maintenance" or vehicle.get("fleetAvailability") == "Maintenance"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle is under maintenance and cannot be booked.",
            )

        maintenance_conditions = [{"vehicle_id": vehicle_id}]
        if vehicle_name:
            maintenance_conditions.append({"vehicle": vehicle_name})
        open_maintenance = db["maintenance"].find(
            {
                "$and": [
                    {"$or": tenant_conditions},
                    {"$or": maintenance_conditions},
                    {"status": {"$nin": ["Completed", "Cancelled"]}},
                ]
            }
        )
        # FIX: Check for date conflicts against all open maintenance jobs
        for record in open_maintenance:
            if self._dates_overlap(start_date, end_date, record.get("start"), record.get("expected") or record.get("start")):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Vehicle has overlapping maintenance and cannot be booked.",
                )

    def check_vehicle_overlap(
        self,
        vehicle_id: str,
        vehicle_name: str,
        start_date: str,
        end_date: str,
        pickup_time: Optional[str] = "10:00",
        return_time: Optional[str] = "10:00",
        exclude_booking_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        req_p = (pickup_time or "10:00").strip()
        req_r = (return_time or "10:00").strip()
        req_start_iso = f"{start_date.strip()}T{req_p}"
        req_end_iso = f"{end_date.strip()}T{req_r}"

        # 1. MongoDB check
        db = self._get_db()
        if db is not None:
            try:
                if vehicle_id:
                    v_query: dict[str, Any] = {
                        "$or": [
                            {"vehicle_details.id": vehicle_id},
                            {"vehicle_id": vehicle_id},
                        ],
                        "status": {"$nin": ["Cancelled", "Completed"]},
                    }
                else:
                    v_query: dict[str, Any] = {
                        "$or": [
                            {"vehicle_details.name": vehicle_name},
                            {"vehicle": vehicle_name},
                        ],
                        "status": {"$nin": ["Cancelled", "Completed"]},
                    }
                if exclude_booking_id:
                    v_query["id"] = {"$ne": exclude_booking_id}

                candidates = list(db["bookings"].find(v_query))
                for c in candidates:
                    r_details = c.get("rental_details") or {}
                    c_start = r_details.get("start_date") or c.get("startDate")
                    c_end = r_details.get("end_date") or c.get("endDate")
                    if c_start and c_end:
                        c_p = (r_details.get("pickup_time") or "10:00").strip()
                        c_r = (r_details.get("return_time") or "10:00").strip()
                        c_start_iso = f"{c_start}T{c_p}"
                        c_end_iso = f"{c_end}T{c_r}"
                        if req_start_iso < c_end_iso and c_start_iso < req_end_iso:
                            return c
            except Exception as e:
                logger.warning("Could not check MongoDB booking overlap: %s", e)

        # 2. In-memory check
        if self._memory_bookings:
            for b_id, b_data in self._memory_bookings.items():
                if exclude_booking_id and b_id == exclude_booking_id:
                    continue
                if b_data.get("status") in ["Cancelled", "Completed"]:
                    continue

                if vehicle_id:
                    existing_v_id = b_data.get("vehicle_details", {}).get("id") or b_data.get("vehicle_id")
                    if existing_v_id != vehicle_id:
                        continue
                else:
                    v_match = (
                        b_data.get("vehicle") == vehicle_name
                        or b_data.get("vehicle_details", {}).get("name") == vehicle_name
                    )
                    if not v_match:
                        continue

                r_details = b_data.get("rental_details") or {}
                c_start = r_details.get("start_date") or b_data.get("startDate")
                c_end = r_details.get("end_date") or b_data.get("endDate")
                if c_start and c_end:
                    c_p = (r_details.get("pickup_time") or "10:00").strip()
                    c_r = (r_details.get("return_time") or "10:00").strip()
                    c_start_iso = f"{c_start}T{c_p}"
                    c_end_iso = f"{c_end}T{c_r}"
                    if req_start_iso < c_end_iso and c_start_iso < req_end_iso:
                        return b_data

        return None

    def create_offline_booking(self, payload: OfflineBookingCreate, tenant_id: Optional[str] = None) -> OfflineBookingResponse:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        # 1. Validate vehicle is bookable before booking creation begins (maintenance check)
        self.assert_vehicle_bookable(
            payload.vehicle.vehicle_id,
            payload.rental.start_date,
            payload.rental.end_date,
            tenant_id,
            payload.vehicle.vehicle_name,
        )

        # 2. Check timing overlap with existing active bookings for this vehicle
        conflict = self.check_vehicle_overlap(
            vehicle_id=payload.vehicle.vehicle_id,
            vehicle_name=payload.vehicle.vehicle_name,
            start_date=payload.rental.start_date,
            end_date=payload.rental.end_date,
            pickup_time=payload.rental.pickup_time,
            return_time=payload.rental.return_time,
            tenant_id=tenant_id,
        )
        if conflict:
            conf_dates = conflict.get("dates") or f"{conflict.get('rental_details', {}).get('start_date')} to {conflict.get('rental_details', {}).get('end_date')}"
            raise ValueError(f"Vehicle '{payload.vehicle.vehicle_name}' is already booked for an overlapping period ({conf_dates}). Please select another vehicle or different rental dates.")
        
        booking_id = f"BK-{int(time.time() * 1000) % 1000000:06d}"
        customer_id = payload.customer.customer_id or f"CU-{int(time.time() * 1000) % 100000:05d}"
        
        rental_days = self._calculate_days(payload.rental.start_date, payload.rental.end_date)
        daily_price = float(payload.vehicle.price_per_day)
        
        base_amount = self._round_money(daily_price * rental_days)
        add_on_amount = self._round_money(500.0 * rental_days) if payload.rental.add_ons else 0.0
        service_fee = self._round_money(base_amount * 0.05)
        subtotal = self._round_money(base_amount + add_on_amount + service_fee)
        discount_amount = self._round_money(min(subtotal, max(0.0, float(payload.rental.discount))))
        deposit_amount = self._round_money(2000.0 if payload.payment.deposit else 0.0)
        total_amount = self._round_money(subtotal - discount_amount + deposit_amount)

        requested_advance = self._round_money(min(total_amount, float(payload.payment.paid_amount)))
        if requested_advance > 0 and not tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required to record an advance payment.")
        if requested_advance > 0 and payload.payment.method.strip().lower() != "cash" and not (payload.payment.transaction_reference or "").strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Transaction reference is required for a non-Cash advance payment.")
        if requested_advance > 0 and self._get_db() is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable. Cannot record advance payment.")
        initial_paid = 0.0
        pending_amount = total_amount
        
        dates_formatted = self._format_date_range(payload.rental.start_date, payload.rental.end_date)
        
        customer_details = {
            "id": customer_id,
            "name": payload.customer.name.strip(),
            "phone": payload.customer.phone.strip(),
            "email": payload.customer.email.strip() if payload.customer.email else "",
        }
        aadhaar_number = payload.customer.aadhaar.strip()
        driving_licence_number = (payload.customer.driving_licence or "").strip() or None
        
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
            "initial_paid": 0.0,
            "transactions": [],
        }
        
        record: dict[str, Any] = {
            "id": booking_id,
            "customer": payload.customer.name.strip(),
            "vehicle": payload.vehicle.vehicle_name,
            "dates": dates_formatted,
            "type": "Offline",
            "status": "Confirmed",
            "paid": initial_paid,
            "pending": pending_amount,
            "base_amount": base_amount,
            "add_on_amount": add_on_amount,
            "service_fee": service_fee,
            "discount_amount": discount_amount,
            "deposit_amount": deposit_amount,
            "total_amount": total_amount,
            "finalTotalAmount": total_amount,
            "rental_days": rental_days,
            "vehicle_details": vehicle_details,
            "customer_details": customer_details,
            "aadhaar_number": aadhaar_number,
            "driving_licence_number": driving_licence_number,
            "rental_details": rental_details,
            "payment_details": payment_details,
            "notes": payload.notes,
            "tenant_id": tenant_id,
            "vendor_id": tenant_id,
            "created_at": now_str,
            "updated_at": now_str,
        }
        
        # Save to Mongo with ACID transaction if available, else save to memory store
        db = self._get_db()
        client = self._get_client()

        if db is not None:
            try:
                with mongo_transaction(client) as session:
                    # 1. Mark vehicle as Rented upon booking creation
                    v_ident = payload.vehicle.vehicle_id or payload.vehicle.vehicle_name
                    if v_ident:
                        conds: list[dict[str, Any]] = [{"id": v_ident}, {"_id": v_ident}, {"makeModel": v_ident}, {"name": v_ident}]
                        try:
                            if ObjectId.is_valid(v_ident):
                                conds.append({"_id": ObjectId(v_ident)})
                        except Exception:
                            pass
                        db["vehicles"].update_many(
                            {"$or": conds},
                            {"$set": {"fleetAvailability": "Rented", "availability": "Rented", "updatedAt": now_str}},
                            session=session,
                        )

                    # 2. Persist booking document
                    db["bookings"].replace_one(
                        {"id": booking_id},
                        {**record, "_id": booking_id},
                        upsert=True,
                        session=session,
                    )

                    # 3. Auto-sync or create customer in customers module collection
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

                    c_conds: list[dict[str, Any]] = []
                    if payload.customer.customer_id:
                        if ObjectId.is_valid(payload.customer.customer_id):
                            c_conds.append({"_id": ObjectId(payload.customer.customer_id)})
                        else:
                            c_conds.append({"id": payload.customer.customer_id})
                    if phone_norm:
                        c_conds.append({"phone_normalized": phone_norm})
                    if phone_raw:
                        c_conds.append({"phone": phone_raw})
                    if c_email:
                        c_conds.append({"email": c_email})

                    if c_conds:
                        cust_query["$or"] = c_conds
                    else:
                        cust_query["name"] = c_name

                    now_utc = datetime.now(timezone.utc)
                    existing_cust = db["customers"].find_one(cust_query, session=session)
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
                                "aadhaar_number": aadhaar_number,
                                "driving_licence_number": driving_licence_number,
                            },
                        }
                        if c_email and not existing_cust.get("email"):
                            update_ops["$set"]["email"] = c_email
                        db["customers"].update_one({"_id": existing_cust["_id"]}, update_ops, session=session)
                        customer_details["id"] = str(existing_cust["_id"])
                        record["customer_details"]["id"] = str(existing_cust["_id"])
                    else:
                        new_cust: dict[str, Any] = {
                            "name": c_name,
                            "phone": phone_raw,
                            "phone_normalized": phone_norm,
                            "email": c_email,
                            "aadhaar_number": aadhaar_number,
                            "driving_licence_number": driving_licence_number,
                            "status": "Verified",
                            "bookings": 1,
                            "active": 0,
                            "paid": 0.0,
                            "pending": float(pending_amount),
                            "created_at": now_utc,
                            "updated_at": now_utc,
                        }
                        if t_id_val is not None:
                            new_cust["tenant_id"] = t_id_val
                        ins_res = db["customers"].insert_one(new_cust, session=session)
                        customer_details["id"] = str(ins_res.inserted_id)
                        record["customer_details"]["id"] = str(ins_res.inserted_id)

                    # 4. Insert initial payment record into payments collection atomically
                    if initial_paid > 0 and payment_details.get("transactions"):
                        first_tx = payment_details["transactions"][0]
                        initial_tx_doc: dict[str, Any] = {
                            "id": first_tx["id"],
                            "_id": first_tx["id"],
                            "booking": booking_id,
                            "customer": payload.customer.name.strip(),
                            "method": payload.payment.method,
                            "date": now_str,
                            "amount": float(initial_paid),
                            "status": "Paid" if pending_amount == 0 else "Partial",
                            "notes": f"Initial counter payment for booking {booking_id}",
                            "tenant_id": str(tenant_id) if tenant_id else None,
                            "vendor_id": str(tenant_id) if tenant_id else None,
                            "created_at": now_str,
                            "updated_at": now_str,
                        }
                        db["payments"].replace_one(
                            {"id": first_tx["id"]},
                            initial_tx_doc,
                            upsert=True,
                            session=session,
                        )
            except Exception as exc:
                logger.error("Transaction failed during booking creation, rolled back: %s", exc)
                raise

        try:
            from app.modules.notifications.service import create_notification
            b_tenant = tenant_id or getattr(payload, "tenant_id", None)
            create_notification(
                title="Booking Confirmed",
                message=f"Booking {booking_id} confirmed for {payload.customer.name}.",
                notification_type="booking",
                severity="success",
                entity_id=booking_id,
                entity_type="booking",
                tenant_id=str(b_tenant) if b_tenant else None,
            )
        except Exception:
            pass
        
        self._memory_bookings[booking_id] = record
        if requested_advance > 0:
            try:
                from app.modules.payments.schemas import PaymentCreate
                from app.modules.payments.service import payment_service
                payment_service.record_payment(
                    PaymentCreate(
                        booking_id=booking_id,
                        amount=requested_advance,
                        method=payload.payment.method,
                        transaction_reference=(payload.payment.transaction_reference or "").strip() or None,
                        idempotency_key=f"advance-{booking_id}",
                    ),
                    tenant_id=tenant_id,
                )
                if db is not None:
                    saved = db["bookings"].find_one({"id": booking_id})
                    if saved:
                        saved.pop("_id", None)
                        record = saved
            except HTTPException as exc:
                record["advancePaymentError"] = exc.detail
                if db is not None:
                    db["bookings"].update_one({"id": booking_id}, {"$set": {"advancePaymentError": exc.detail}})
            except Exception:
                record["advancePaymentError"] = "Advance payment could not be recorded."
                if db is not None:
                    db["bookings"].update_one({"id": booking_id}, {"$set": {"advancePaymentError": record["advancePaymentError"]}})
        return OfflineBookingResponse.model_validate(self._enrich_booking_payment_fields(record))

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
                    return OfflineBookingResponse.model_validate(self._enrich_booking_payment_fields(doc))
            except Exception as exc:
                logger.error("Failed to get booking from Mongo: %s", exc)

        if booking_id in self._memory_bookings:
            b = self._memory_bookings[booking_id]
            if tenant_id and b.get("tenant_id") and b.get("tenant_id") != tenant_id:
                return None
            return OfflineBookingResponse.model_validate(self._enrich_booking_payment_fields(b))
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

        return [OfflineBookingResponse.model_validate(self._enrich_booking_payment_fields(item)) for item in results]

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

        # Update in Mongo with ACID transaction
        db = self._get_db()
        client = self._get_client()
        if db is not None:
            try:
                with mongo_transaction(client) as session:
                    db["bookings"].update_one(
                        {"$or": [{"id": booking_id}, {"_id": booking_id}]},
                        {"$set": update_dict},
                        session=session,
                    )

                    # When booking completes (bike returned), vehicle goes to 'Under Review' for inspection
                    if payload.status == "Completed":
                        v_id = booking.vehicle_details.get("id") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "id", None)
                        v_reg = booking.vehicle_details.get("registration") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "registration", None)
                        v_ident = v_id or booking.vehicle
                        if v_ident or v_reg:
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
                                    session=session,
                                )

                    # When booking is cancelled, vehicle goes back to 'Available'
                    elif payload.status == "Cancelled":
                        v_id = booking.vehicle_details.get("id") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "id", None)
                        v_reg = booking.vehicle_details.get("registration") if isinstance(booking.vehicle_details, dict) else getattr(booking.vehicle_details, "registration", None)
                        v_ident = v_id or booking.vehicle
                        if v_ident or v_reg:
                            conds = []
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
                                    {"$set": {"fleetAvailability": "Available", "availability": "Available", "updatedAt": update_dict["updated_at"]}},
                                    session=session,
                                )

                    # Update customer active count if booking ended
                    if payload.status in ("Completed", "Cancelled"):
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
                                session=session,
                            )
            except Exception as exc:
                logger.error("Failed to update booking with transaction in Mongo: %s", exc)

        if payload.status == "Completed":
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

    @staticmethod
    def _tenant_filter(booking_id: str, tenant_id: str, expected_status: str | list[str]) -> dict[str, Any]:
        statuses = expected_status if isinstance(expected_status, list) else [expected_status]
        return {
            "$and": [
                {"$or": [{"id": booking_id}, {"_id": booking_id}]},
                {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}]},
                {"status": {"$in": statuses}},
            ]
        }

    @staticmethod
    def _ownership_filter(booking_id: str, tenant_id: str) -> dict[str, Any]:
        return {"$and": [{"$or": [{"id": booking_id}, {"_id": booking_id}]}, {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}]}]}

    @staticmethod
    def _vehicle_filter(booking: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        details = booking.get("vehicle_details") or {}
        vehicle_id = str(details.get("id") or booking.get("vehicle") or "")
        registration = str(details.get("registration") or "")
        refs: list[dict[str, Any]] = [{"id": vehicle_id}, {"_id": vehicle_id}, {"makeModel": vehicle_id}, {"name": vehicle_id}]
        if registration:
            refs.extend([{"registration": registration}, {"registrationNumber": registration}])
        if ObjectId.is_valid(vehicle_id):
            refs.append({"_id": ObjectId(vehicle_id)})
        return {"$and": [{"$or": refs}, {"$or": [{"tenantId": tenant_id}, {"tenant_id": tenant_id}, {"vendor_id": tenant_id}]}]}

    # FIX: Helper to verify if vehicle has active/ongoing maintenance jobs
    def _has_open_maintenance(self, db, booking: dict[str, Any], tenant_id: str) -> bool:
        details = booking.get("vehicle_details") or {}
        vehicle_id = details.get("id") or booking.get("vehicle")
        return db["maintenance"].find_one(
            {
                "$and": [
                    {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}]},
                    {"$or": [{"vehicle_id": vehicle_id}, {"vehicle": booking.get("vehicle")}]},
                    {"status": {"$nin": ["Completed", "Cancelled"]}},
                ]
            }
        ) is not None

    @staticmethod
    def _action_time(value: Optional[datetime]) -> datetime:
        action_time = value or datetime.now(timezone.utc)
        if action_time.tzinfo is None:
            action_time = action_time.replace(tzinfo=timezone.utc)
        action_time = action_time.astimezone(timezone.utc)
        if action_time > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise HTTPException(status_code=422, detail="Lifecycle timestamp cannot be in the future.")
        return action_time

    def _response_from_doc(self, doc: dict[str, Any]) -> OfflineBookingResponse:
        doc = dict(doc)
        doc.pop("_id", None)
        additional = sum(int(round(float(item.get("amount", 0)) * 100)) for item in doc.get("additionalCharges", []))
        total = self._round_money(float(doc.get("total_amount", 0.0)))
        paid = self._round_money(float(doc.get("paid", 0.0)))
        doc["finalTotalAmount"] = total
        doc["finalBill"] = {
            "base": doc.get("base_amount", 0.0), "discount": doc.get("discount_amount", 0.0),
            "deposit": doc.get("deposit_amount", 0.0), "additionalCharges": self._round_money(additional / 100),
            "finalTotal": total, "paid": paid, "outstanding": self._round_money(max(0, total - paid)),
        }
        return OfflineBookingResponse.model_validate(self._enrich_booking_payment_fields(doc))

    def handover_booking(self, booking_id: str, payload: LifecycleActionRequest, tenant_id: str) -> OfflineBookingResponse:
        db = self._get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")
        if not db["bookings"].find_one(self._ownership_filter(booking_id, tenant_id)):
            raise HTTPException(status_code=404, detail="Booking not found.")
        booking = db["bookings"].find_one(self._tenant_filter(booking_id, tenant_id, "Confirmed"))
        if not booking:
            raise HTTPException(status_code=409, detail="Handover requires a Confirmed booking.")
        # FIX: Block vehicle handover if vehicle was put under maintenance while confirmed
        if self._has_open_maintenance(db, booking, tenant_id):
            raise HTTPException(status_code=409, detail="Vehicle is under maintenance and cannot be handed over.")
        vehicle_id = (booking.get("vehicle_details") or {}).get("id") or booking.get("vehicle")
        other = db["bookings"].find_one({"$and": [{"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}]}, {"status": {"$in": ["Active", "Returned"]}}, {"id": {"$ne": booking_id}}, {"$or": [{"vehicle_details.id": vehicle_id}, {"vehicle": booking.get("vehicle")}]}]})
        if other:
            raise HTTPException(status_code=409, detail="Vehicle is already held by another active booking.")
        now = self._action_time(payload.occurred_at).isoformat()
        claim_filter = {"$and": [self._vehicle_filter(booking, tenant_id), {"$or": [{"fleetAvailability": "Available"}, {"availability": "Available"}, {"fleetAvailability": {"$exists": False}}, {"availability": {"$exists": False}}]}]}
        claimed = db["vehicles"].find_one_and_update(claim_filter, {"$set": {"fleetAvailability": "Rented", "availability": "Rented", "updatedAt": now}}, return_document=ReturnDocument.AFTER)
        if not claimed:
            raise HTTPException(status_code=409, detail="Vehicle is not available for handover.")
        updated = db["bookings"].find_one_and_update(self._tenant_filter(booking_id, tenant_id, "Confirmed"), {"$set": {"status": "Active", "handoverAt": now, "handoverNotes": payload.notes, "updated_at": now}}, return_document=ReturnDocument.AFTER)
        if not updated:
            db["vehicles"].update_one({"_id": claimed["_id"], "fleetAvailability": "Rented"}, {"$set": {"fleetAvailability": "Available", "availability": "Available", "updatedAt": now}})
            raise HTTPException(status_code=409, detail="Booking is no longer Confirmed; handover was not applied.")
        return self._response_from_doc(updated)

    def return_booking(self, booking_id: str, payload: ReturnBookingRequest, tenant_id: str) -> OfflineBookingResponse:
        db = self._get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")
        if not db["bookings"].find_one(self._ownership_filter(booking_id, tenant_id)):
            raise HTTPException(status_code=404, detail="Booking not found.")
        booking = db["bookings"].find_one(self._tenant_filter(booking_id, tenant_id, "Active"))
        if not booking:
            raise HTTPException(status_code=409, detail="Return requires an Active booking.")
        returned = self._action_time(payload.occurred_at)
        if booking.get("handoverAt"):
            handover = datetime.fromisoformat(str(booking["handoverAt"]).replace("Z", "+00:00"))
            if returned < handover.astimezone(timezone.utc):
                raise HTTPException(status_code=422, detail="Return time cannot be before handover time.")
        rental = booking.get("rental_details") or {}
        late_paise = 0
        try:
            due = datetime.combine(date.fromisoformat(rental["end_date"]), datetime_time.fromisoformat(rental.get("return_time") or "10:00"), tzinfo=timezone(timedelta(hours=5, minutes=30))) + timedelta(minutes=LATE_GRACE_MINUTES)
            returned_ist = returned.astimezone(timezone(timedelta(hours=5, minutes=30)))
            late_seconds = (returned_ist - due).total_seconds()
            if late_seconds > 0:
                late_days = max(1, int((late_seconds + 86399) // 86400))
                late_paise = late_days * int(round(float((booking.get("vehicle_details") or {}).get("price_per_day", 0)) * 100))
        except Exception:
            late_paise = 0
        manual_paise = int(round(float(payload.extra_charges) * 100))
        if manual_paise and not (payload.extra_charge_reason or "").strip():
            raise HTTPException(status_code=422, detail="A reason is required for manual extra charges.")
        charge_items: list[dict[str, Any]] = []
        stamp = returned.isoformat()
        if late_paise:
            charge_items.append({"amount": self._round_money(late_paise / 100), "reason": "Late return", "type": "late", "createdAt": stamp})
        if manual_paise:
            charge_items.append({"amount": self._round_money(manual_paise / 100), "reason": payload.extra_charge_reason.strip(), "type": "manual", "createdAt": stamp})
        added = self._round_money((late_paise + manual_paise) / 100)
        update: dict[str, Any] = {"$set": {"status": "Returned", "returnedAt": stamp, "returnNotes": payload.notes, "updated_at": stamp, "finalBill": {}}, "$inc": {"total_amount": added, "pending": added, "finalTotalAmount": added}}
        if charge_items:
            update["$push"] = {"additionalCharges": {"$each": charge_items}}
        updated = db["bookings"].find_one_and_update(self._tenant_filter(booking_id, tenant_id, "Active"), update, return_document=ReturnDocument.AFTER)
        if not updated:
            raise HTTPException(status_code=409, detail="Booking is no longer Active; return was not applied.")
        # FIX: On rental return, set vehicle state to Maintenance if open maintenance exists, otherwise Under Review
        vehicle_state = "Maintenance" if self._has_open_maintenance(db, booking, tenant_id) else "Under Review"
        db["vehicles"].update_one(self._vehicle_filter(booking, tenant_id), {"$set": {"fleetAvailability": vehicle_state, "availability": vehicle_state, "updatedAt": stamp}})
        if added:
            customer_id = (booking.get("customer_details") or {}).get("id")
            customer_filter: dict[str, Any] = {"name": booking.get("customer"), "$or": [{"tenant_id": tenant_id}, {"tenant_id": ObjectId(tenant_id) if ObjectId.is_valid(tenant_id) else tenant_id}]}
            if customer_id and ObjectId.is_valid(customer_id):
                customer_filter = {"_id": ObjectId(customer_id)}
            db["customers"].update_one(customer_filter, {"$inc": {"pending": added}, "$set": {"updated_at": datetime.now(timezone.utc)}})
        return self._response_from_doc(updated)

    def complete_booking(self, booking_id: str, payload: LifecycleActionRequest, tenant_id: str) -> OfflineBookingResponse:
        db = self._get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")
        if not db["bookings"].find_one(self._ownership_filter(booking_id, tenant_id)):
            raise HTTPException(status_code=404, detail="Booking not found.")
        stamp = self._action_time(payload.occurred_at).isoformat()
        updated = db["bookings"].find_one_and_update(self._tenant_filter(booking_id, tenant_id, "Returned"), {"$set": {"status": "Completed", "completedAt": stamp, "updated_at": stamp}}, return_document=ReturnDocument.AFTER)
        if not updated:
            raise HTTPException(status_code=409, detail="Completion requires a Returned booking.")
        vehicle_filter = self._vehicle_filter(updated, tenant_id)
        vehicle_id = (updated.get("vehicle_details") or {}).get("id") or updated.get("vehicle")
        holder = db["bookings"].find_one({"$and": [{"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}]}, {"status": {"$in": ["Active", "Returned"]}}, {"id": {"$ne": booking_id}}, {"$or": [{"vehicle_details.id": vehicle_id}, {"vehicle": updated.get("vehicle")}]}]})
        # FIX: On booking completion, set vehicle state to Maintenance if open maintenance exists, otherwise Available
        if not holder:
            vehicle_state = "Maintenance" if self._has_open_maintenance(db, updated, tenant_id) else "Available"
            db["vehicles"].update_one(vehicle_filter, {"$set": {"fleetAvailability": vehicle_state, "availability": vehicle_state, "updatedAt": stamp}})
        return self._response_from_doc(updated)

    def cancel_booking(self, booking_id: str, tenant_id: str) -> OfflineBookingResponse:
        db = self._get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")
        if not db["bookings"].find_one(self._ownership_filter(booking_id, tenant_id)):
            raise HTTPException(status_code=404, detail="Booking not found.")
        stamp = datetime.now(timezone.utc).isoformat()
        updated = db["bookings"].find_one_and_update(self._tenant_filter(booking_id, tenant_id, ["Confirmed", "Active"]), {"$set": {"status": "Cancelled", "updated_at": stamp}}, return_document=ReturnDocument.AFTER)
        if not updated:
            raise HTTPException(status_code=409, detail="Cancellation is allowed only from Confirmed or Active.")
        return self._response_from_doc(updated)

    def record_payment(self, booking_id: str, payment: PaymentRecordCreate, tenant_id: Optional[str] = None) -> Optional[OfflineBookingResponse]:
        from app.modules.payments.service import payment_service
        from app.modules.payments.schemas import PaymentCreate

        idemp_key = payment.idempotency_key or str(uuid.uuid4())
        ref = payment.transaction_reference
        if payment.method.strip().lower() != "cash" and not ref:
            ref = f"REF-{uuid.uuid4().hex[:6].upper()}"

        p_create = PaymentCreate(
            booking_id=booking_id,
            amount=payment.amount,
            method=payment.method,
            notes=payment.notes,
            transaction_reference=ref,
            idempotency_key=idemp_key,
            payment_date=payment.payment_date,
        )
        payment_service.record_payment(p_create, tenant_id=tenant_id)
        return self.get_booking(booking_id, tenant_id=tenant_id)


booking_service = BookingService()
