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
    r"^[A-Z]{2}\d{1,2}[A-Z]{0,4}\d{1,4}$",
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
    Return True if *rc* (already normalised) matches an Indian or standard RC pattern.
    Supports standard state formats (e.g. GJ05AB4821, DL1AB1234), BH series (e.g. 22BH1234AA),
    and general alphanumeric plates (4-16 chars containing letters and numbers).
    """
    if not rc:
        return False
    norm = rc.strip().replace(" ", "").upper()
    if len(norm) < 4 or len(norm) > 16:
        return False
    if _RC_PATTERN.match(norm):
        return True
    if re.match(r"^\d{2}BH\d{1,4}[A-Z]{1,2}$", norm, re.IGNORECASE):
        return True
    if re.match(r"^[A-Z0-9]{4,16}$", norm) and any(c.isdigit() for c in norm) and any(c.isalpha() for c in norm):
        return True
    return False


def check_rc_duplicate(rc: str, db_collection: Any, tenant_id: Optional[str] = None) -> bool:
    """
    Check whether *rc* already exists in the vehicles collection.

    Designed so that callers can pass a PyMongo collection object.
    The query searches the normalised ``registrationNumber`` field.
    If *tenant_id* is provided, checks duplicate within that tenant's fleet.

    Parameters
    ----------
    rc:
        Already-normalised registration number.
    db_collection:
        A PyMongo ``Collection`` instance (or any object with a
        ``.find_one(filter)`` method — useful for testing with mocks).
    tenant_id:
        Optional tenant ID to scope duplicate check per-vendor fleet.

    Returns
    -------
    True if a duplicate is found, False otherwise.
    """
    norm = normalise_rc(rc)
    if tenant_id:
        filter_query: dict[str, Any] = {
            "registrationNumber": norm,
            "$or": [
                {"tenant_id": str(tenant_id)},
                {"tenantId": str(tenant_id)},
            ],
        }
    else:
        filter_query = {"registrationNumber": norm}
    existing = db_collection.find_one(filter_query)
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
