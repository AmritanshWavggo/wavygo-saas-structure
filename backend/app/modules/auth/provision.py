import getpass
import logging
import re

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.db.mongodb import create_mongo_client, get_database
from app.modules.auth.security import hash_password, normalize_email

logger = logging.getLogger(__name__)


def main() -> int:
    email = normalize_email(input("Vendor email: "))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Enter a valid email address.")
        return 2

    password = getpass.getpass("Vendor password (12-128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 2
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        print(str(exc))
        return 2

    client = create_mongo_client()
    if client is None:
        print("MONGODB_URI must be configured to provision a vendor.")
        return 2

    try:
        database = get_database(client)
        if database is None:
            print("MongoDB is not configured.")
            return 2
        vendors = database["vendors"]
        vendors.create_index(
            [("email_normalized", ASCENDING)],
            unique=True,
            name="vendor_email_normalized_unique",
        )
        result = vendors.insert_one(
            {
                "email": email,
                "email_normalized": email,
                "password_hash": password_hash,
                "is_active": True,
            }
        )
    except DuplicateKeyError:
        print("A vendor account with that email already exists.")
        return 1
    except PyMongoError as exc:
        logger.error("Vendor provisioning failed: %s", type(exc).__name__)
        return 1
    finally:
        client.close()

    print(f"Vendor account provisioned with ID {result.inserted_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
