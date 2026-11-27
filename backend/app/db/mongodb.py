from contextlib import contextmanager
from typing import Any, Generator, Optional
import logging
import time

from pymongo import ASCENDING, DESCENDING, MongoClient, ReadPreference
from pymongo.client_session import ClientSession
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

    is_cloud = "mongodb+srv://" in uri or "ssl=true" in uri.lower() or "tls=true" in uri.lower()
    timeout_ms = 8000 if is_cloud else 2000
    connect_timeout_ms = 8000 if is_cloud else 2000

    try:
        import certifi
        client_kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": timeout_ms,
            "connectTimeoutMS": connect_timeout_ms,
        }
        if is_cloud:
            client_kwargs["tlsCAFile"] = certifi.where()
            client_kwargs["tlsAllowInvalidCertificates"] = True
        client = MongoClient(uri, **client_kwargs)
        client.get_database("admin", read_preference=ReadPreference.PRIMARY_PREFERRED).command("ping")
        _mongo_client = client
        _is_connected = True
        return _mongo_client
    except Exception as exc:
        logger.warning("MongoDB primary connect failed: %s", exc)
        if "mongodb+srv://" in uri:
            try:
                fallback_kwargs: dict[str, Any] = {
                    "serverSelectionTimeoutMS": 10000,
                    "connectTimeoutMS": 10000,
                }
                try:
                    import certifi
                    fallback_kwargs["tlsCAFile"] = certifi.where()
                    fallback_kwargs["tlsAllowInvalidCertificates"] = True
                except Exception:
                    pass
                client = MongoClient(uri, **fallback_kwargs)
                client.get_database("admin", read_preference=ReadPreference.PRIMARY_PREFERRED).command("ping")
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


@contextmanager
def mongo_transaction(client: Optional[MongoClient] = None) -> Generator[Optional[ClientSession], None, None]:
    """
    ACID Transaction context manager for MongoDB operations.

    If MongoDB is running as a replica set (e.g. MongoDB Atlas or production cluster),
    it manages a multi-document ACID transaction with automatic commit and rollback on exceptions.
    If running standalone or if client is None, it gracefully yields a standard session
    or None, keeping all development and test environments fully functional.
    """
    if client is None:
        client = create_mongo_client()
    if client is None:
        yield None
        return

    session: Optional[ClientSession] = None
    in_tx: bool = False
    try:
        session = client.start_session()
        try:
            session.start_transaction()
            in_tx = True
            logger.debug("Started MongoDB ACID transaction session.")
        except (OperationFailure, PyMongoError) as tx_err:
            # Standalone MongoDB instances do not support multi-document transactions (error code 20)
            logger.debug("MongoDB topology does not support multi-document transactions (%s). Proceeding in standard session mode.", tx_err)
            in_tx = False

        yield session

        if in_tx and session.in_transaction:
            session.commit_transaction()
            logger.debug("Committed MongoDB ACID transaction successfully.")
    except Exception as exc:
        if in_tx and session is not None and session.in_transaction:
            try:
                session.abort_transaction()
                logger.warning("Aborted/rolled back MongoDB transaction due to exception: %s", exc)
            except Exception as abort_err:
                logger.error("Failed to abort MongoDB transaction: %s", abort_err)
        raise exc
    finally:
        if session is not None:
            try:
                session.end_session()
            except Exception:
                pass


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

    payment_indexes = (
        (
            "uq_payments_tenant_idempotency",
            lambda: payments_col.create_index(
                [("tenant_id", ASCENDING), ("idempotency_key", ASCENDING)],
                name="uq_payments_tenant_idempotency",
                unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}},
            ),
        ),
        (
            "uq_payments_tenant_booking_txn_ref",
            lambda: payments_col.create_index(
                [("tenant_id", ASCENDING), ("booking", ASCENDING), ("transaction_reference", ASCENDING)],
                name="uq_payments_tenant_booking_txn_ref",
                unique=True,
                partialFilterExpression={"transaction_reference": {"$type": "string", "$gt": ""}},
            ),
        ),
        (
            "ix_payments_tenant_created",
            lambda: payments_col.create_index(
                [("tenant_id", ASCENDING), ("created_at", ASCENDING)],
                name="ix_payments_tenant_created",
            ),
        ),
    )
    for index_name, create_fn in payment_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create payment index %s: %s", index_name, exc)


def ensure_booking_indexes() -> None:
    """Create DBMS indexes on the bookings collection for queries, overlap checks, and ordering."""
    db = get_database()
    if db is None:
        return
    bookings_col = db["bookings"]

    booking_indexes = (
        (
            "uq_bookings_id",
            lambda: bookings_col.create_index(
                [("id", ASCENDING)],
                name="uq_bookings_id",
                unique=True,
                sparse=True,
            ),
        ),
        (
            "ix_bookings_tenant_status",
            lambda: bookings_col.create_index(
                [("tenant_id", ASCENDING), ("status", ASCENDING)],
                name="ix_bookings_tenant_status",
            ),
        ),
        (
            "ix_bookings_overlap_lookup",
            lambda: bookings_col.create_index(
                [
                    ("tenant_id", ASCENDING),
                    ("vehicle_details.id", ASCENDING),
                    ("status", ASCENDING),
                ],
                name="ix_bookings_overlap_lookup",
            ),
        ),
        (
            "ix_bookings_rental_dates",
            lambda: bookings_col.create_index(
                [
                    ("tenant_id", ASCENDING),
                    ("rental_details.start_date", ASCENDING),
                    ("rental_details.end_date", ASCENDING),
                ],
                name="ix_bookings_rental_dates",
            ),
        ),
        (
            "ix_bookings_customer_phone",
            lambda: bookings_col.create_index(
                [("tenant_id", ASCENDING), ("customer_details.phone", ASCENDING)],
                name="ix_bookings_customer_phone",
            ),
        ),
        (
            "ix_bookings_created",
            lambda: bookings_col.create_index(
                [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
                name="ix_bookings_created",
            ),
        ),
    )
    for index_name, create_fn in booking_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create booking index %s: %s", index_name, exc)


def ensure_customer_indexes() -> None:
    """Create DBMS indexes on the customers collection for unique phone numbers, email, and lookup."""
    db = get_database()
    if db is None:
        return
    customers_col = db["customers"]

    customer_indexes = (
        (
            "uq_customers_tenant_phone",
            lambda: customers_col.create_index(
                [("tenant_id", ASCENDING), ("phone", ASCENDING)],
                name="uq_customers_tenant_phone",
                unique=True,
                sparse=True,
            ),
        ),
        (
            "ix_customers_phone_normalized",
            lambda: customers_col.create_index(
                [("tenant_id", ASCENDING), ("phone_normalized", ASCENDING)],
                name="ix_customers_phone_normalized",
                sparse=True,
            ),
        ),
        (
            "ix_customers_email",
            lambda: customers_col.create_index(
                [("tenant_id", ASCENDING), ("email", ASCENDING)],
                name="ix_customers_email",
                sparse=True,
            ),
        ),
        (
            "ix_customers_name",
            lambda: customers_col.create_index(
                [("tenant_id", ASCENDING), ("name", ASCENDING)],
                name="ix_customers_name",
            ),
        ),
        (
            "ix_customers_created",
            lambda: customers_col.create_index(
                [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
                name="ix_customers_created",
            ),
        ),
    )
    for index_name, create_fn in customer_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create customer index %s: %s", index_name, exc)


def ensure_auth_indexes() -> None:
    """Create DBMS indexes for users, vendors, sessions, and security."""
    db = get_database()
    if db is None:
        return

    # Vendors/Users unique email
    try:
        db["vendors"].create_index(
            [("email", ASCENDING)],
            name="uq_vendors_email",
            unique=True,
            sparse=True,
        )
    except Exception as exc:
        logger.error("Failed to create vendors email index: %s", exc)

    try:
        db["users"].create_index(
            [("email", ASCENDING)],
            name="uq_users_email",
            unique=True,
            sparse=True,
        )
    except Exception as exc:
        logger.error("Failed to create users email index: %s", exc)

    # Security sessions index
    try:
        db["security_sessions"].create_index(
            [("vendor_id", ASCENDING), ("expires_at", ASCENDING)],
            name="ix_security_sessions_expiry",
        )
    except Exception as exc:
        logger.error("Failed to create security sessions index: %s", exc)

    # Login attempts TTL / lookup index
    try:
        db["security_login_attempts"].create_index(
            [("key", ASCENDING), ("updated_at", ASCENDING)],
            name="ix_security_login_attempts_key",
        )
    except Exception as exc:
        logger.error("Failed to create login attempts index: %s", exc)


def ensure_staff_indexes() -> None:
    """Create DBMS indexes on staff collection."""
    db = get_database()
    if db is None:
        return
    staff_col = db["staff"]
    staff_indexes = (
        ("ix_staff_tenant_phone", lambda: staff_col.create_index([("tenant_id", ASCENDING), ("phone", ASCENDING)], name="ix_staff_tenant_phone")),
        ("ix_staff_tenant_email", lambda: staff_col.create_index([("tenant_id", ASCENDING), ("email", ASCENDING)], name="ix_staff_tenant_email", sparse=True)),
        ("ix_staff_tenant_role", lambda: staff_col.create_index([("tenant_id", ASCENDING), ("role", ASCENDING)], name="ix_staff_tenant_role")),
    )
    for index_name, create_fn in staff_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create staff index %s: %s", index_name, exc)


def ensure_document_indexes() -> None:
    """Create DBMS indexes on documents collection."""
    db = get_database()
    if db is None:
        return
    docs_col = db["documents"]
    doc_indexes = (
        ("ix_documents_tenant_scope_entity", lambda: docs_col.create_index([("tenant_id", ASCENDING), ("scope", ASCENDING), ("entity_id", ASCENDING)], name="ix_documents_tenant_scope_entity")),
        ("ix_documents_tenant_status", lambda: docs_col.create_index([("tenant_id", ASCENDING), ("status", ASCENDING)], name="ix_documents_tenant_status")),
    )
    for index_name, create_fn in doc_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create document index %s: %s", index_name, exc)


def ensure_maintenance_indexes() -> None:
    """Create DBMS indexes on maintenance collection."""
    db = get_database()
    if db is None:
        return
    maint_col = db["maintenance"]
    maint_indexes = (
        ("ix_maintenance_tenant_vehicle", lambda: maint_col.create_index([("tenant_id", ASCENDING), ("vehicle_id", ASCENDING), ("status", ASCENDING)], name="ix_maintenance_tenant_vehicle")),
        ("ix_maintenance_tenant_start", lambda: maint_col.create_index([("tenant_id", ASCENDING), ("start", ASCENDING)], name="ix_maintenance_tenant_start")),
    )
    for index_name, create_fn in maint_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create maintenance index %s: %s", index_name, exc)


def ensure_finance_indexes() -> None:
    """Create DBMS indexes on finance / expenses collection."""
    db = get_database()
    if db is None:
        return
    exp_col = db["expenses"]
    exp_indexes = (
        ("ix_expenses_tenant_date", lambda: exp_col.create_index([("tenant_id", ASCENDING), ("date", DESCENDING)], name="ix_expenses_tenant_date")),
        ("ix_expenses_tenant_category", lambda: exp_col.create_index([("tenant_id", ASCENDING), ("category", ASCENDING)], name="ix_expenses_tenant_category")),
    )
    for index_name, create_fn in exp_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create expense index %s: %s", index_name, exc)


def ensure_notification_indexes() -> None:
    """Create DBMS indexes on notifications collection."""
    db = get_database()
    if db is None:
        return
    notif_col = db["notifications"]
    notif_indexes = (
        ("ix_notifications_tenant_read", lambda: notif_col.create_index([("tenant_id", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)], name="ix_notifications_tenant_read")),
    )
    for index_name, create_fn in notif_indexes:
        try:
            create_fn()
        except Exception as exc:
            logger.error("Failed to create notification index %s: %s", index_name, exc)


def ensure_all_indexes() -> dict[str, bool]:
    """
    Execute index creation across all DBMS collections.
    Returns status map for each domain index setup.
    """
    results: dict[str, bool] = {}
    runners = [
        ("vehicles", ensure_vehicle_indexes),
        ("payments", ensure_payment_indexes),
        ("bookings", ensure_booking_indexes),
        ("customers", ensure_customer_indexes),
        ("auth", ensure_auth_indexes),
        ("staff", ensure_staff_indexes),
        ("maintenance", ensure_maintenance_indexes),
        ("documents", ensure_document_indexes),
        ("finance", ensure_finance_indexes),
        ("notifications", ensure_notification_indexes),
    ]
    for domain, runner in runners:
        try:
            runner()
            results[domain] = True
        except Exception as exc:
            logger.error("Index initialization failed for %s: %s", domain, exc)
            results[domain] = False
    logger.info("Database indexes ensured across all collections.")
    return results
