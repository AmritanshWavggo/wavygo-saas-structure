from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import error_payload

logger = logging.getLogger(__name__)


def _format_validation_errors(errors: Any) -> list[dict[str, str]]:
    if not isinstance(errors, (list, tuple)):
        return [{"field": "general", "message": str(errors)}]
    formatted = []
    for err in errors:
        if isinstance(err, dict):
            loc = err.get("loc", [])
            field = str(loc[-1]) if loc else "general"
            msg = err.get("msg") or err.get("message") or str(err)
            formatted.append({"field": field, "message": msg})
        else:
            formatted.append({"field": "general", "message": str(err)})
    return formatted


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "TOO_MANY_REQUESTS",
        }.get(exc.status_code, "REQUEST_ERROR")

        details = None
        if exc.status_code == 422 and isinstance(exc.detail, (list, tuple)):
            details = _format_validation_errors(exc.detail)
            message = "Validation failed."
        else:
            message = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(error_payload(code, message, details=details)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = _format_validation_errors(exc.errors())
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                error_payload("VALIDATION_ERROR", "Request validation failed.", details=details)
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        logger.exception("Unhandled request error request_id=%s", request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_ERROR", "An unexpected error occurred."),
        )
