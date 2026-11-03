from __future__ import annotations

import argparse
import getpass
import re
from datetime import datetime, timezone

from pymongo import MongoClient

from app.core.config import settings
from app.modules.auth.service import hash_password, normalize_email


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a WavyGo tenant and its first owner.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password")
    parser.add_argument("--slug")
    args = parser.parse_args()
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is required.")
    password = args.password or getpass.getpass("Owner password: ")
    email = normalize_email(args.email)
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    if db["users"].find_one({"email": email}):
        raise SystemExit("A user with that email already exists.")
    slug = args.slug or slugify(args.name)
    if not slug:
        raise SystemExit("A valid tenant slug is required.")
    now = datetime.now(timezone.utc)
    tenant_id = db["tenants"].insert_one({"name": args.name.strip(), "slug": slug, "status": "active", "createdAt": now, "updatedAt": now}).inserted_id
    try:
        owner_id = db["users"].insert_one({"tenantId": tenant_id, "email": email, "passwordHash": hash_password(password), "role": "owner", "isActive": True, "createdAt": now, "updatedAt": now, "createdBy": None}).inserted_id
        db["users"].update_one({"_id": owner_id}, {"$set": {"createdBy": owner_id}})
    except Exception:
        db["tenants"].delete_one({"_id": tenant_id})
        raise
    print(f"tenant_id={tenant_id}")
    print(f"owner_id={owner_id}")


if __name__ == "__main__":
    main()
