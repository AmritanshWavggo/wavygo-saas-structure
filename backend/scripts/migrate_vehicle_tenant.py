from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign unscoped vehicles to one seeded tenant.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not ObjectId.is_valid(args.tenant_id):
        raise SystemExit("--tenant-id must be an ObjectId.")
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is required.")
    db = MongoClient(settings.mongodb_uri)[settings.mongodb_database]
    tenant_id = ObjectId(args.tenant_id)
    owner = db["users"].find_one({"tenantId": tenant_id, "role": "owner", "isActive": True})
    if owner is None:
        raise SystemExit("No active owner exists for this tenant.")
    documents = list(db["vehicles"].find({"tenantId": {"$exists": False}}))
    registrations = [doc.get("registrationNumber") for doc in documents if doc.get("registrationNumber")]
    existing_registrations = [
        doc.get("registrationNumber")
        for doc in db["vehicles"].find({"tenantId": tenant_id, "deletedAt": None})
        if doc.get("registrationNumber")
    ]
    duplicates = [
        registration
        for registration, count in Counter(registrations + existing_registrations).items()
        if count > 1
    ]
    if duplicates:
        print("Aborting: duplicate registrationNumber values found:")
        for registration in duplicates:
            print(registration)
        raise SystemExit(1)
    print(f"{len(documents)} vehicle document(s) would be assigned to tenant {tenant_id}.")
    if args.dry_run:
        return
    result = db["vehicles"].update_many({"tenantId": {"$exists": False}}, {"$set": {"tenantId": tenant_id, "createdBy": owner["_id"], "deletedAt": None, "updatedAt": datetime.now(timezone.utc)}})
    print(f"Migrated {result.modified_count} vehicle document(s).")


if __name__ == "__main__":
    main()
