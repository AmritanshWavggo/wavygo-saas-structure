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


def ensure_vehicle_indexes() -> None:
    """
    Create required indexes on the vehicles collection.

    Called once at application startup.  Idempotent — if the index already
    exists with the same name and options, PyMongo is a no-op.

    Index created:
        uq_registration_number — sparse unique index on ``registrationNumber``
        (camelCase alias actually stored in MongoDB).
        Sparse so that documents without the field are not rejected.
    """
    db = get_database()
    if db is None:
        logger.warning(
            "MongoDB not configured — skipping vehicle index creation. "
            "Set MONGODB_URI in your environment."
        )
        return

    collection = db["vehicles"]
    index_name = "uq_registration_number"
    try:
        collection.create_index(
            [(("registrationNumber"), ASCENDING)],
            unique=True,
            sparse=True,
            name=index_name,
        )
        logger.info("Vehicle index '%s' is ready.", index_name)
    except (DuplicateKeyError, OperationFailure, PyMongoError) as exc:
        # OperationFailure code 85 = index already exists with different options.
        # DuplicateKeyError = existing data already has duplicate registrationNumber values.
        logger.error(
            "Could not create vehicle index '%s'. "
            "This usually means the vehicles collection already contains duplicate "
            "registrationNumber values that must be resolved before the index can be "
            "applied.  The application will continue running without the unique constraint. "
            "Error: %s",
            index_name,
            exc,
        )
