import logging

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_mongo_client() -> MongoClient | None:
    """Create a client only when explicitly requested and configured."""
    if not settings.mongodb_uri:
        return None
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)


def get_database(client: MongoClient | None = None) -> Database | None:
    """Return the configured database, without connecting during app import."""
    if client is None:
        client = create_mongo_client()
    if client is None:
        return None
    return client[settings.mongodb_database]


def ensure_indexes() -> None:
    """
    Create required indexes on all collections (tenants, users, refresh_tokens, vehicles, customers).

    Called once at application startup. Idempotent — if the index already
    exists with the same name and options, PyMongo is a no-op.
    """
    db = get_database()
    if db is None:
        logger.warning(
            "MongoDB not configured — skipping index creation. "
            "Set MONGODB_URI in your environment."
        )
        return

    try:
        db["tenants"].create_index([("slug", ASCENDING)], unique=True, name="uq_tenant_slug")
        db["users"].create_index([("email", ASCENDING)], unique=True, name="uq_user_email")
        db["users"].create_index([("tenantId", ASCENDING), ("role", ASCENDING)], name="ix_users_tenant_role")
        db["refresh_tokens"].create_index([("tokenHash", ASCENDING)], unique=True, name="uq_refresh_token_hash")
        db["refresh_tokens"].create_index([("userId", ASCENDING), ("expiresAt", ASCENDING)], name="ix_refresh_user_expiry")
        db["refresh_tokens"].create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="ttl_refresh_expiry")
        vehicles = db["vehicles"]
        existing_indexes = {index["name"] for index in vehicles.list_indexes()}
        if "uq_registration_number" in existing_indexes:
            vehicles.drop_index("uq_registration_number")
            logger.info("Replaced legacy global vehicle registration index.")
        vehicles.create_index([("tenantId", ASCENDING), ("deletedAt", ASCENDING)], name="ix_vehicles_tenant_deleted")
        vehicles.create_index(
            [("tenantId", ASCENDING), ("registrationNumber", ASCENDING)],
            unique=True,
            partialFilterExpression={"deletedAt": {"$type": "null"}, "registrationNumber": {"$type": "string"}},
            name="uq_vehicle_tenant_registration_active",
        )
        customers = db["customers"]
        customers.create_index(
            [("tenantId", ASCENDING), ("deletedAt", ASCENDING), ("createdAt", ASCENDING)],
            name="ix_customers_tenant_deleted_created",
        )
        customers.create_index(
            [("tenantId", ASCENDING), ("phone", ASCENDING)],
            unique=True,
            partialFilterExpression={"deletedAt": {"$type": "null"}, "phone": {"$type": "string"}},
            name="uq_customer_tenant_phone_active",
        )
        logger.info("Database security indexes are ready.")
    except (DuplicateKeyError, OperationFailure, PyMongoError) as exc:
        # OperationFailure code 85 = index already exists with different options.
        # DuplicateKeyError = existing data already has duplicate registrationNumber / phone values.
        logger.error(
            "Could not create database indexes: %s. Run scripts.migrate_vehicle_tenant --dry-run "
            "and resolve duplicate values.",
            exc,
        )
        raise RuntimeError("Database indexes could not be created; refusing to start.") from exc


ensure_vehicle_indexes = ensure_indexes
