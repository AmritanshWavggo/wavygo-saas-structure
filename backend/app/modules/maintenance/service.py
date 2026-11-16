from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Optional, List, Dict, Any

from app.db.mongodb import get_database
from app.modules.maintenance.schemas import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceResponse,
    MaintenanceStatsResponse,
    VehicleReviewStatusUpdate,
)


class MaintenanceService:
    def __init__(self):
        # In-memory store fallback when MongoDB is unavailable (local dev & tests)
        self._memory_maintenance: Dict[str, Dict[str, Any]] = {}
        self._seed_default_maintenance()

    def _get_db(self):
        try:
            return get_database()
        except Exception:
            return None

    def _seed_default_maintenance(self):
        initial = [
            {
                "id": "MT-081",
                "vehicle_id": "VH-1022",
                "vehicle": "Yamaha FZ-S FI",
                "registration": "GJ 05 JK 8610",
                "type": "Scheduled servicing",
                "damage_details": "Periodic engine tuning, oil check and brake pad calibration.",
                "issue": "Periodic servicing",
                "start": "Oct 12, 2026",
                "expected": "Oct 14, 2026",
                "cost": 2400.0,
                "payment": "Paid",
                "status": "Ongoing",
                "mechanic_name": "Raju Auto Works",
                "notes": "Mechanic flagged slight front disc wear, replaced.",
                "created_at": "2026-10-12T09:00:00",
                "updated_at": "2026-10-12T09:00:00",
            },
            {
                "id": "MT-080",
                "vehicle_id": "VH-1029",
                "vehicle": "TVS Jupiter",
                "registration": "GJ 05 GH 2351",
                "type": "Brake inspection",
                "damage_details": "Rear drum brake cable loose and low friction shoe.",
                "issue": "Rear brake loose",
                "start": "Oct 10, 2026",
                "expected": "Oct 11, 2026",
                "cost": 950.0,
                "payment": "Paid",
                "status": "Completed",
                "mechanic_name": "City Bike Care",
                "notes": "Tested and passed post-service road inspection.",
                "created_at": "2026-10-10T10:30:00",
                "updated_at": "2026-10-11T16:00:00",
            },
            {
                "id": "MT-079",
                "vehicle_id": "VH-1034",
                "vehicle": "Ather 450X",
                "registration": "GJ 05 EF 3602",
                "type": "Tyre replacement",
                "damage_details": "Puncture in rear tubeless tyre with sidewall cut.",
                "issue": "Rear tyre sidewall damage",
                "start": "Oct 07, 2026",
                "expected": "Oct 08, 2026",
                "cost": 3800.0,
                "payment": "Pending",
                "status": "Completed",
                "mechanic_name": "EV Tech Station",
                "notes": "Installed new MRF Zapper tyre.",
                "created_at": "2026-10-07T14:00:00",
                "updated_at": "2026-10-08T18:00:00",
            },
            {
                "id": "MT-078",
                "vehicle_id": "VH-1042",
                "vehicle": "Honda Activa 6G",
                "registration": "GJ 05 AB 4821",
                "type": "Oil change",
                "damage_details": "Regular 5000 km oil flush and air filter cleaning.",
                "issue": "Regular maintenance",
                "start": "Oct 02, 2026",
                "expected": "Oct 02, 2026",
                "cost": 680.0,
                "payment": "Paid",
                "status": "Completed",
                "mechanic_name": "Express Lube",
                "notes": "Clean inspection, ready for rental.",
                "created_at": "2026-10-02T11:00:00",
                "updated_at": "2026-10-02T13:30:00",
            },
        ]
        for item in initial:
            self._memory_maintenance[item["id"]] = item

    def _update_vehicle_availability_internal(self, vehicle_id_or_name: str, availability: str):
        """Update vehicle availability in MongoDB and memory."""
        db = self._get_db()
        if db is not None:
            try:
                # Try finding by id, _id, or makeModel / name
                db["vehicles"].update_many(
                    {
                        "$or": [
                            {"id": vehicle_id_or_name},
                            {"_id": vehicle_id_or_name},
                            {"makeModel": vehicle_id_or_name},
                            {"name": vehicle_id_or_name},
                        ]
                    },
                    {
                        "$set": {
                            "fleetAvailability": availability,
                            "availability": availability,
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
            except Exception:
                pass

    def create_maintenance(self, payload: MaintenanceCreate, tenant_id: Optional[str] = None) -> MaintenanceResponse:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        # Generate sequential / timestamp-based MT ID
        existing_nums = []
        for mid in self._memory_maintenance.keys():
            if mid.startswith("MT-"):
                try:
                    existing_nums.append(int(mid.split("-")[1]))
                except Exception:
                    pass
        next_num = max(existing_nums, default=81) + 1
        m_id = f"MT-{next_num:03d}"

        # Standardise damage / issue details
        damage = payload.damage_details or payload.issue or "Damaged during rental, sent for inspection & repairs."

        record: Dict[str, Any] = {
            "id": m_id,
            "vehicle_id": payload.vehicle_id,
            "vehicle": payload.vehicle.strip(),
            "registration": payload.registration.strip() if payload.registration else None,
            "type": payload.type.strip() if payload.type else "Damage Repair",
            "damage_details": damage.strip(),
            "issue": payload.issue.strip() if payload.issue else damage.strip(),
            "start": payload.start.strip(),
            "expected": payload.expected.strip() if payload.expected else None,
            "cost": float(payload.cost),
            "payment": payload.payment.strip() if payload.payment else "Pending",
            "status": payload.status.strip() if payload.status else "Ongoing",
            "mechanic_name": payload.mechanic_name.strip() if payload.mechanic_name else None,
            "notes": payload.notes.strip() if payload.notes else None,
            "tenant_id": tenant_id,
            "vendor_id": tenant_id,
            "created_at": now_str,
            "updated_at": now_str,
        }

        # 1. Update vehicle status to "Maintenance"
        vehicle_identifier = payload.vehicle_id or payload.vehicle
        self._update_vehicle_availability_internal(vehicle_identifier, "Maintenance")

        # 2. Persist in Mongo
        db = self._get_db()
        if db is not None:
            try:
                db["maintenance"].replace_one({"id": m_id}, {**record, "_id": m_id}, upsert=True)
            except Exception:
                pass

        try:
            from app.modules.notifications.service import create_notification
            create_notification(
                title="Vehicle Sent to Maintenance",
                message=f"{payload.vehicle} sent to maintenance: {payload.type or damage}.",
                notification_type="maintenance",
                severity="warning",
                entity_id=m_id,
                entity_type="maintenance",
                tenant_id=str(tenant_id) if tenant_id else None,
            )
        except Exception:
            pass

        # 3. Save in-memory
        self._memory_maintenance[m_id] = record
        return MaintenanceResponse(**record)

    def list_maintenance(
        self,
        status: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[MaintenanceResponse]:
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
                if vehicle_id:
                    v_cond = [{"vehicle_id": vehicle_id}, {"vehicle": vehicle_id}]
                    if "$or" in mongo_filter:
                        mongo_filter["$and"] = [{"$or": mongo_filter.pop("$or")}, {"$or": v_cond}]
                    else:
                        mongo_filter["$or"] = v_cond
                if query:
                    regex_q = {"$regex": query, "$options": "i"}
                    q_cond = [
                        {"id": regex_q},
                        {"vehicle": regex_q},
                        {"type": regex_q},
                        {"damage_details": regex_q},
                        {"mechanic_name": regex_q},
                    ]
                    if "$or" in mongo_filter:
                        mongo_filter["$and"] = [{"$or": mongo_filter.pop("$or")}, {"$or": q_cond}]
                    else:
                        mongo_filter["$or"] = q_cond
                cursor = db["maintenance"].find(mongo_filter).sort("created_at", -1).skip(skip).limit(limit)
                for doc in cursor:
                    doc.pop("_id", None)
                    results.append(doc)
            except Exception:
                pass

        # Fallback to in-memory store if DB is unreachable or for unauthenticated test suites
        if not results and (db is None or not tenant_id):
            for item in sorted(self._memory_maintenance.values(), key=lambda x: x.get("created_at", ""), reverse=True):
                if tenant_id and (item.get("tenant_id") != tenant_id and item.get("vendor_id") != tenant_id):
                    continue
                if status and status.lower() != "all" and item.get("status") != status:
                    continue
                if vehicle_id and item.get("vehicle_id") != vehicle_id and item.get("vehicle") != vehicle_id:
                    continue
                if query:
                    q_lower = query.lower()
                    target = f"{item.get('id', '')} {item.get('vehicle', '')} {item.get('type', '')} {item.get('damage_details', '')} {item.get('mechanic_name', '')}".lower()
                    if q_lower not in target:
                        continue
                results.append(item)
            results = results[skip: skip + limit]

        return [MaintenanceResponse(**item) for item in results]

    def get_maintenance(self, maintenance_id: str, tenant_id: Optional[str] = None) -> Optional[MaintenanceResponse]:
        db = self._get_db()
        if db is not None:
            try:
                filt: dict[str, Any] = {"$or": [{"id": maintenance_id}, {"_id": maintenance_id}]}
                if tenant_id:
                    filt = {"$and": [filt, {"$or": [{"tenant_id": tenant_id}, {"vendor_id": tenant_id}, {"tenant_id": None}, {"vendor_id": None}]}]}
                doc = db["maintenance"].find_one(filt)
                if doc:
                    doc.pop("_id", None)
                    return MaintenanceResponse(**doc)
            except Exception:
                pass

        if maintenance_id in self._memory_maintenance:
            m = self._memory_maintenance[maintenance_id]
            if tenant_id and m.get("tenant_id") and m.get("tenant_id") != tenant_id:
                return None
            return MaintenanceResponse(**m)
        return None

    def update_maintenance(self, maintenance_id: str, payload: MaintenanceUpdate, tenant_id: Optional[str] = None) -> Optional[MaintenanceResponse]:
        existing = self.get_maintenance(maintenance_id, tenant_id=tenant_id)
        if not existing:
            return None

        now_str = datetime.now(timezone.utc).isoformat()
        update_dict: Dict[str, Any] = {"updated_at": now_str}

        if payload.type is not None:
            update_dict["type"] = payload.type
        if payload.damage_details is not None:
            update_dict["damage_details"] = payload.damage_details
        if payload.issue is not None:
            update_dict["issue"] = payload.issue
        if payload.start is not None:
            update_dict["start"] = payload.start
        if payload.expected is not None:
            update_dict["expected"] = payload.expected
        if payload.cost is not None:
            update_dict["cost"] = float(payload.cost)
        if payload.payment is not None:
            update_dict["payment"] = payload.payment
        if payload.status is not None:
            update_dict["status"] = payload.status
            # If changed to Completed, release vehicle back to Available
            if payload.status == "Completed":
                self._update_vehicle_availability_internal(existing.vehicle_id or existing.vehicle, "Available")
                try:
                    from app.modules.notifications.service import create_notification
                    m_tenant = tenant_id or getattr(existing, "tenant_id", None) or getattr(existing, "vendor_id", None)
                    create_notification(
                        title="Maintenance Completed",
                        message=f"{existing.vehicle} repairs completed. Vehicle is now Available.",
                        notification_type="vehicle",
                        severity="success",
                        entity_id=maintenance_id,
                        entity_type="vehicle",
                        tenant_id=str(m_tenant) if m_tenant else None,
                    )
                except Exception:
                    pass
        if payload.mechanic_name is not None:
            update_dict["mechanic_name"] = payload.mechanic_name
        if payload.notes is not None:
            update_dict["notes"] = payload.notes

        # Update in Mongo
        db = self._get_db()
        if db is not None:
            try:
                db["maintenance"].update_one({"$or": [{"id": maintenance_id}, {"_id": maintenance_id}]}, {"$set": update_dict})
            except Exception:
                pass

        # Update in memory
        if maintenance_id in self._memory_maintenance:
            self._memory_maintenance[maintenance_id].update(update_dict)

        return self.get_maintenance(maintenance_id) or MaintenanceResponse(**{**existing.dict(), **update_dict})

    def complete_maintenance(self, maintenance_id: str, return_to_available: bool = True) -> Optional[MaintenanceResponse]:
        """Mark maintenance job as completed and release vehicle back to Available."""
        existing = self.get_maintenance(maintenance_id)
        if not existing:
            return None

        update_payload = MaintenanceUpdate(status="Completed")
        res = self.update_maintenance(maintenance_id, update_payload)

        if return_to_available:
            self._update_vehicle_availability_internal(existing.vehicle_id or existing.vehicle, "Available")

        return res

    def delete_maintenance(self, maintenance_id: str) -> bool:
        db = self._get_db()
        if db is not None:
            try:
                res = db["maintenance"].delete_one({"$or": [{"id": maintenance_id}, {"_id": maintenance_id}]})
                if res.deleted_count > 0:
                    self._memory_maintenance.pop(maintenance_id, None)
                    return True
            except Exception:
                pass

        if maintenance_id in self._memory_maintenance:
            del self._memory_maintenance[maintenance_id]
            return True
        return False

    def update_vehicle_review_status(self, vehicle_id_or_payload: Any, status: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(vehicle_id_or_payload, str):
            v_id = vehicle_id_or_payload
            st = status or "Available"
            nt = notes
        else:
            v_id = getattr(vehicle_id_or_payload, "vehicle_id", str(vehicle_id_or_payload))
            st = getattr(vehicle_id_or_payload, "status", status or "Available")
            nt = getattr(vehicle_id_or_payload, "notes", notes)
        self._update_vehicle_availability_internal(v_id, st)
        return {
            "vehicle_id": v_id,
            "status": st,
            "notes": nt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Vehicle status updated to '{st}'.",
        }

    def get_stats(self, tenant_id: Optional[str] = None) -> MaintenanceStatsResponse:
        records = self.list_maintenance(limit=1000, tenant_id=tenant_id)
        open_count = sum(1 for r in records if r.status == "Ongoing")
        completed_count = sum(1 for r in records if r.status == "Completed")
        total_costs = sum(r.cost for r in records)

        return MaintenanceStatsResponse(
            open_jobs=open_count,
            completed_jobs=completed_count,
            total_cost=total_costs,
            total_jobs=len(records),
        )


maintenance_service = MaintenanceService()
