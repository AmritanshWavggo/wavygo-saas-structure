import mongomock

from scripts.backfill_vehicle_availability import run


def test_backfill_is_dry_run_by_default_and_idempotent_after_apply(capsys):
    db = mongomock.MongoClient()["backfill"]
    db["vehicles"].insert_many([
        {"_id": "VH-1", "id": "VH-1", "tenant_id": "tenant-a", "availability": "Available", "fleetAvailability": "Rented"},
        {"_id": "VH-2", "id": "VH-2", "tenant_id": "tenant-a", "availability": "Available", "fleetAvailability": "Available"},
    ])
    db["maintenance"].insert_one({"id": "MT-1", "tenant_id": "tenant-a", "vehicle_id": "VH-2", "status": "Ongoing"})

    assert run(db) == 2
    assert db["vehicles"].find_one({"id": "VH-1"})["availability"] == "Available"
    assert "Dry run" in capsys.readouterr().out

    assert run(db, apply=True) == 2
    assert db["vehicles"].find_one({"id": "VH-1"})["availability"] == "Rented"
    state = db["vehicles"].find_one({"id": "VH-2"})
    assert state["availability"] == state["fleetAvailability"] == "Maintenance"
    assert run(db) == 0
