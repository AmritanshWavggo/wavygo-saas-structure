from __future__ import annotations

import logging
import re
from datetime import datetime, date, timezone
import time
import uuid
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.db.mongodb import create_mongo_client, get_database, mongo_transaction
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

        # Check timing overlap with existing active bookings for this vehicle
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

        initial_paid = self._round_money(min(total_amount, float(payload.payment.paid_amount)))
        pending_amount = self._round_money(max(0.0, total_amount - initial_paid))
        
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
                            "active": 1,
                            "paid": float(initial_paid),
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
