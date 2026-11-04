import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_mongo_client() -> MongoClient | None:
    """Create a client only when explicitly requested and configured."""
    if not settings.mongodb_uri:
        return None
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )


def check_replica_set(client: MongoClient | None = None) -> None:
    """
    Ensure production MongoDB is running as a replica set so multi-document transactions work.
    Skipped strictly when APP_ENV == 'testing'.
    Uses admin command 'hello' and requires 'setName'.
    """
    if settings.app_env == "testing":
        return

    if client is None:
        client = create_mongo_client()

    if client is None:
        return

    try:
        hello_doc = client.admin.command("hello")
        if "setName" not in hello_doc:
            raise RuntimeError(
                "MongoDB is not running as a replica set (missing 'setName' in hello response). "
                "Transactions require a replica set."
            )
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Failed to verify MongoDB replica set status: {exc}") from exc


def get_database(client: MongoClient | None = None) -> Database | None:
    """Return the configured database, without connecting during app import."""
    if client is None:
        client = create_mongo_client()
    if client is None:
        return None
    return client[settings.mongodb_database]


def ensure_indexes() -> None:
    """
    Create required indexes on all collections (tenants, users, refresh_tokens, vehicles, customers, bookings, counters).

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

        counters = db["counters"]
        counters.create_index(
            [("tenantId", ASCENDING), ("sequence", ASCENDING)],
            unique=True,
            name="uq_counters_tenant_sequence",
        )

        bookings = db["bookings"]
        bookings.create_index(
            [("tenantId", ASCENDING), ("bookingNumber", ASCENDING)],
            unique=True,
            name="uq_bookings_tenant_number",
        )
        bookings.create_index(
            [("tenantId", ASCENDING), ("vehicleId", ASCENDING), ("status", ASCENDING), ("startDate", ASCENDING), ("endDate", ASCENDING)],
            name="ix_bookings_overlap_scan",
        )
        bookings.create_index(
            [("tenantId", ASCENDING), ("customerId", ASCENDING)],
            name="ix_bookings_tenant_customer",
        )
        bookings.create_index(
            [("tenantId", ASCENDING), ("deletedAt", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)],
            name="ix_bookings_tenant_deleted_status_created",
        )
        bookings.create_index(
            [("tenantId", ASCENDING), ("vehicleId", ASCENDING)],
            unique=True,
            partialFilterExpression={"status": "Active", "deletedAt": {"$type": "null"}},
            name="uq_bookings_tenant_vehicle_active",
        )

        logger.info("Database security and domain indexes are ready.")
    except (DuplicateKeyError, OperationFailure, PyMongoError) as exc:
        logger.error(
            "Could not create database indexes: %s. Run scripts.migrate_vehicle_tenant --dry-run "
            "and resolve duplicate values.",
            exc,
        )
        raise RuntimeError("Database indexes could not be created; refusing to start.") from exc


ensure_vehicle_indexes = ensure_indexes
