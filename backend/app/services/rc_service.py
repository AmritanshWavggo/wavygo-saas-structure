"""
RC (registration certificate / number) service.

Handles normalisation and duplicate checking for vehicle registration numbers.
The public interface is intentionally shaped so that an external RC lookup API
(e.g. Vahan / Parivahan) can be plugged in later without changing call sites.

No external API calls are made here.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Pattern: Indian registration numbers.
# Format: <state-code> <district-code> <series> <number>
# Examples: GJ05AB4821, KA01MN2345, MH02AB1234
# Spaces are stripped before validation, so "GJ 05 AB 4821" also matches.
# ---------------------------------------------------------------------------
_RC_PATTERN = re.compile(
    r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$",
    re.IGNORECASE,
)


def normalise_rc(raw: str) -> str:
    """
    Normalise a raw registration number string.

    Strips all whitespace and converts to uppercase.

    Parameters
    ----------
    raw:
        The registration number as entered by the user.

    Returns
    -------
    Normalised string (e.g. "GJ05AB4821").
    """
    return raw.strip().replace(" ", "").upper()


def validate_rc_format(rc: str) -> bool:
    """
    Return True if *rc* (already normalised) matches the expected RC pattern.

    The pattern covers standard Indian registration plates.  Custom / special
    plates that don't match will return False — callers decide how to handle.
    """
    return bool(_RC_PATTERN.match(rc))


def check_rc_duplicate(rc: str, db_collection: Any) -> bool:
    """
    Check whether *rc* already exists in the vehicles collection.

    Designed so that callers can pass a PyMongo collection object.
    The query searches the normalised ``registration_number`` field.

    Parameters
    ----------
    rc:
        Already-normalised registration number.
    db_collection:
        A PyMongo ``Collection`` instance (or any object with a
        ``.find_one(filter)`` method — useful for testing with mocks).

    Returns
    -------
    True if a duplicate is found, False otherwise.
    """
    existing = db_collection.find_one({"registrationNumber": rc})
    return existing is not None


def lookup_rc_info(rc: str) -> Optional[dict[str, Any]]:
    """
    Placeholder for future RC lookup via an external API (e.g. Vahan/Parivahan).

    Currently returns None — the caller should treat None as "no external data
    available" and proceed with whatever the user submitted.

    When an RC API is integrated, replace the body of this function with the
    actual HTTP call.  The return shape should be:
        {
            "owner":      str,
            "make_model": str,
            "year":       int,
            "fuel":       str,
            "valid":      bool,
            ...           (any additional API fields)
        }
    or None if the API returns no record for the given plate.

    Parameters
    ----------
    rc:
        Already-normalised registration number.
    """
    # TODO: plug in Vahan/Parivahan API here
    return None
