"""
Cloudinary service.

Provides upload, delete, and bulk-delete helpers.
All credentials are read exclusively from environment variables:

  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET

Never hardcode secrets here.
"""

from __future__ import annotations

import os
from typing import Any

import cloudinary
import cloudinary.uploader

# ---------------------------------------------------------------------------
# Configure the SDK from environment variables at import time.
# The SDK reads the config object on every call, so this is sufficient.
# ---------------------------------------------------------------------------
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", ""),
    secure=True,
)


def upload_file(file_bytes: bytes, folder: str, **kwargs: Any) -> dict[str, Any]:
    """
    Upload a file to Cloudinary under the given folder.

    Parameters
    ----------
    file_bytes:
        Raw bytes of the file to upload (from python-multipart / FastAPI UploadFile).
    folder:
        Cloudinary folder path, e.g. "wavygo/vehicles/photos".
    **kwargs:
        Additional options forwarded to cloudinary.uploader.upload
        (e.g. resource_type="raw" for PDF documents).

    Returns
    -------
    dict with at minimum:
        url        – secure HTTPS URL of the uploaded asset
        public_id  – Cloudinary public ID needed to delete or transform later
    """
    missing = [
        name
        for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise RuntimeError(
            f"Cloudinary is not configured. "
            f"Set the following environment variable(s): {', '.join(missing)}"
        )
    result: dict[str, Any] = cloudinary.uploader.upload(
        file_bytes,
        folder=folder,
        **kwargs,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }


def delete_file(public_id: str, **kwargs: Any) -> dict[str, Any]:
    """
    Delete a single asset from Cloudinary by its public ID.

    Parameters
    ----------
    public_id:
        The Cloudinary public ID returned by upload_file().
    **kwargs:
        Additional options forwarded to cloudinary.uploader.destroy
        (e.g. resource_type="raw" for PDFs).

    Returns
    -------
    Cloudinary API response dict (contains a "result" key: "ok" on success).
    """
    return cloudinary.uploader.destroy(public_id, **kwargs)  # type: ignore[return-value]


def delete_files(public_ids: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    """
    Delete multiple Cloudinary assets.

    Calls delete_file() for each ID individually so that a failure on one
    asset does not silently skip the rest.  Callers should handle exceptions
    per item if partial failure tolerance is needed.

    Parameters
    ----------
    public_ids:
        List of Cloudinary public IDs to delete.
    **kwargs:
        Forwarded to each delete_file() call.

    Returns
    -------
    List of Cloudinary API response dicts, one per public_id.
    """
    return [delete_file(pid, **kwargs) for pid in public_ids]
