"""
Upload middleware for vehicle files.

FastAPI uses python-multipart for file uploads (UploadFile).
This module provides:
  - Constants for allowed MIME types and size limits
  - Dependency functions that validate incoming files before they reach
    a route handler (plug in as FastAPI dependencies in Phase 2)

No multer here — the Python equivalent is python-multipart + FastAPI's
UploadFile, which is already bundled with uvicorn[standard].
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, UploadFile, status

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

#: Maximum size for a vehicle photo upload (5 MB)
MAX_PHOTO_SIZE_BYTES: int = 5 * 1024 * 1024

#: Maximum size for a compliance document upload (10 MB — PDFs can be larger)
MAX_DOCUMENT_SIZE_BYTES: int = 10 * 1024 * 1024

#: Allowed MIME types for vehicle photos
ALLOWED_PHOTO_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)

#: Allowed MIME types for compliance documents (images + PDF)
ALLOWED_DOCUMENT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _validate_file(
    file: UploadFile,
    allowed_types: frozenset[str],
    max_bytes: int,
    label: str,
) -> UploadFile:
    """Shared validation logic — raises HTTP 422 on violations."""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid {label} file type '{file.content_type}'. "
                f"Allowed: {sorted(allowed_types)}."
            ),
        )
    # content-length header may not be set by all clients, so we also
    # check file.size when available (FastAPI populates it after reading).
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{label.capitalize()} file exceeds the {max_bytes // (1024 * 1024)} MB limit."
            ),
        )
    return file


async def validate_photo_upload(file: UploadFile) -> UploadFile:
    """
    FastAPI dependency — validates a vehicle photo upload.

    Usage in a route (Phase 2):
        @router.post("/vehicles/{vehicle_id}/photos")
        async def upload_photo(file: Annotated[UploadFile, Depends(validate_photo_upload)]):
            ...
    """
    return _validate_file(
        file,
        allowed_types=ALLOWED_PHOTO_MIME_TYPES,
        max_bytes=MAX_PHOTO_SIZE_BYTES,
        label="photo",
    )


async def validate_document_upload(file: UploadFile) -> UploadFile:
    """
    FastAPI dependency — validates a compliance document upload.

    Allows images and PDFs up to MAX_DOCUMENT_SIZE_BYTES.

    Usage in a route (Phase 2):
        @router.post("/vehicles/{vehicle_id}/documents")
        async def upload_document(file: Annotated[UploadFile, Depends(validate_document_upload)]):
            ...
    """
    return _validate_file(
        file,
        allowed_types=ALLOWED_DOCUMENT_MIME_TYPES,
        max_bytes=MAX_DOCUMENT_SIZE_BYTES,
        label="document",
    )


# Annotated type aliases for cleaner route signatures in Phase 2
ValidatedPhoto = Annotated[UploadFile, Depends(validate_photo_upload)]
ValidatedDocument = Annotated[UploadFile, Depends(validate_document_upload)]
