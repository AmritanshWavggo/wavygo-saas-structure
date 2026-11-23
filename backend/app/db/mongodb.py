from typing import Any, Optional
import logging
import time

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[MongoClient] = None
_last_check_time: float = 0.0
_is_connected: bool = False


def create_mongo_client() -> Optional[MongoClient]:
    """Create a client or return existing connected client pool."""
    global _mongo_client, _last_check_time, _is_connected

    uri = settings.effective_mongo_uri
    if not uri:
        return None

    # Return cached client if connected
    if _is_connected and _mongo_client is not None:
        return _mongo_client

    now = time.time()
    # If connection previously failed, throttle for 10 seconds before retrying
    if not _is_connected and (now - _last_check_time) < 10.0:
        return None

    _last_check_time = now

    try:
        import certifi
        client_kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": 2000,
            "connectTimeoutMS": 2000,
        }
        if "mongodb+srv://" in uri or "ssl=true" in uri.lower() or "tls=true" in uri.lower():
            client_kwargs["tlsCAFile"] = certifi.where()
            client_kwargs["tlsAllowInvalidCertificates"] = True
        client = MongoClient(uri, **client_kwargs)
        client.admin.command("ping")
        _mongo_client = client
        _is_connected = True
        return _mongo_client
    except Exception as exc:
        logger.warning("MongoDB primary connect failed: %s", exc)
        if "mongodb+srv://" in uri:
            try:
                client = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=2000,
                    connectTimeoutMS=2000,
                )
                client.admin.command("ping")
                _mongo_client = client
                _is_connected = True
                return _mongo_client
            except Exception as exc2:
                logger.warning("MongoDB fallback ping failed: %s", exc2)
        _is_connected = False
        _mongo_client = None
        return None


def get_database(client: Optional[MongoClient] = None) -> Optional[Database]:
    """Return the configured database, without crashing if connection fails."""
    try:
        if client is None:
            client = create_mongo_client()
        if client is None:
            return None
        return client[settings.mongodb_database]
    except Exception:
        return None


def ensure_vehicle_indexes() -> None:
    """
    Create required indexes on the vehicles collection.

    Called once at application startup. Idempotent.
    """
    db = get_database()
    if db is None:
        logger.warning(
            "MongoDB not configured — skipping vehicle index creation. "
            "Set MONGODB_URI in your environment."
        )
        return

    try:
        vehicles_col = db["vehicles"]
        # Drop legacy global unique index if present so it doesn't conflict across tenants or on nulls
        try:
            for idx in vehicles_col.list_indexes():
                iname = idx.get("name", "")
                ikey = idx.get("key", {})
                if iname in ("uq_registration_number", "registrationNumber_1", "registration_number_1") or (
                    idx.get("unique")
                    and "tenant_id" not in ikey
                    and "tenantId" not in ikey
                    and ("registrationNumber" in ikey or "registration" in ikey)
                ):
                    try:
                        vehicles_col.drop_index(iname)
                        logger.info("Dropped legacy global vehicle index: %s", iname)
                    except Exception:
                        pass
        except Exception:
            pass

        # Unique sparse index on registrationNumber: prevents duplicate
        # registrations per-tenant. Sparse so vehicles without a registration
        # (legacy drafts) do not conflict.
        vehicles_col.create_index(
            [("tenant_id", ASCENDING), ("registrationNumber", ASCENDING)],
            unique=True,
            sparse=True,
            name="uq_tenant_registration",
        )
        # Search index on name, registration, color
        vehicles_col.create_index(
            [("name", ASCENDING), ("registration", ASCENDING)],
            name="ix_vehicle_search",
        )
        # Filter indexes
        vehicles_col.create_index([("type", ASCENDING)], name="ix_vehicle_type")
        vehicles_col.create_index([("fuel", ASCENDING)], name="ix_vehicle_fuel")
        vehicles_col.create_index(
            [("fleetAvailability", ASCENDING)], name="ix_vehicle_availability"
        )
        vehicles_col.create_index(
            [("showOnWavygo", ASCENDING)], name="ix_vehicle_show_on_wavygo"
        )
    except (DuplicateKeyError, OperationFailure) as exc:
        logger.warning("Vehicle index creation warning: %s", exc)
    except PyMongoError as exc:
        logger.error("Failed to ensure vehicle indexes: %s", exc)


def ensure_payment_indexes() -> None:
    """
    Create required indexes on payments collection.
    Idempotent and safe for existing data with partialFilterExpression.
    """
    db = get_database()
    if db is None:
        logger.warning("MongoDB not configured — skipping payment index creation.")
        return

    payments_col = db["payments"]

    # Check existing data for reference conflicts before creating unique index.
    try:
        pipeline = [
            {"$match": {"transaction_reference": {"$type": "string", "$gt": ""}}},
            {
                "$group": {
                    "_id": {
                        "tenant_id": "$tenant_id",
                        "booking": "$booking",
                        "ref": "$transaction_reference",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
        dups = list(payments_col.aggregate(pipeline))
        if dups:
            logger.warning("Existing duplicate transaction references detected: %s", dups)
    except Exception as check_exc:
        logger.debug("Payment duplicate check skipped: %s", check_exc)

    indexes = (
        (
            "uq_payments_tenant_idempotency",
            [("tenant_id", ASCENDING), ("idempotency_key", ASCENDING)],
            {
                "unique": True,
                "partialFilterExpression": {"idempotency_key": {"$type": "string", "$gt": ""}},
            },
        ),
        (
            "uq_payments_tenant_booking_txn_ref",
            [("tenant_id", ASCENDING), ("booking", ASCENDING), ("transaction_reference", ASCENDING)],
            {
                "unique": True,
                "partialFilterExpression": {"transaction_reference": {"$type": "string", "$gt": ""}},
            },
        ),
        ("ix_payments_tenant_created", [("tenant_id", ASCENDING), ("created_at", ASCENDING)], {}),
    )
    for index_name, keys, options in indexes:
        try:
            payments_col.create_index(keys, name=index_name, **options)
        except Exception as exc:
            logger.error("Failed to create payment index %s: %s", index_name, exc)
