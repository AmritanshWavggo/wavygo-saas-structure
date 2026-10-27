import getpass
import logging
import re

from pymongo.errors import PyMongoError

from app.db.mongodb import create_mongo_client, get_database
from app.modules.auth.security import hash_password, normalize_email

logger = logging.getLogger(__name__)


def main() -> int:
    email = normalize_email(input("Vendor email: "))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Enter a valid email address.")
        return 2

    password = getpass.getpass("New password (12-128 characters): ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 2
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        print(str(exc))
        return 2

    try:
        client = create_mongo_client()
    except PyMongoError as exc:
        logger.error("Vendor password reset failed (%s).", type(exc).__name__)
        print("Could not connect to the vendor database.")
        return 1

    if client is None:
        print("MONGODB_URI must be configured to reset a vendor password.")
        return 2

    try:
        database = get_database(client)
        if database is None:
            print("MongoDB is not configured.")
            return 2

        result = database["vendors"].update_one(
            {"email_normalized": email},
            {"$set": {"password_hash": password_hash}},
        )
        if result.matched_count != 1:
            print("No matching vendor account was found.")
            return 1
    except PyMongoError as exc:
        logger.error("Vendor password reset failed (%s).", type(exc).__name__)
        print("Could not update the vendor password.")
        return 1
    finally:
        client.close()

    print("Vendor password updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
