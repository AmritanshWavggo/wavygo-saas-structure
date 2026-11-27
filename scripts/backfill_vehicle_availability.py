"""
Backfill vehicle availability script to harmonize availability and fleetAvailability,
taking ongoing maintenance into account.
"""

def run(db, apply: bool = False) -> int:
    vehicles = list(db["vehicles"].find({}))
    ongoing_maintenance = {
        m["vehicle_id"]: m
        for m in db["maintenance"].find({"status": "Ongoing"})
        if "vehicle_id" in m
    }

    updates = []
    for v in vehicles:
        vid = v.get("id") or v.get("_id")
        current_avail = v.get("availability")
        current_fleet = v.get("fleetAvailability")

        if vid in ongoing_maintenance:
            target_avail = "Maintenance"
            target_fleet = "Maintenance"
        else:
            target_avail = current_fleet or current_avail
            target_fleet = current_fleet or current_avail

        if current_avail != target_avail or current_fleet != target_fleet:
            updates.append((v["_id"], target_avail, target_fleet))

    if not apply:
        print(f"Dry run: {len(updates)} vehicles need updating.")
        return len(updates)

    for doc_id, target_avail, target_fleet in updates:
        db["vehicles"].update_one(
            {"_id": doc_id},
            {"$set": {"availability": target_avail, "fleetAvailability": target_fleet}},
        )

    print(f"Applied updates to {len(updates)} vehicles.")
    return len(updates)
