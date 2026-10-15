from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings


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
