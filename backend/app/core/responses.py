from __future__ import annotations

from typing import Any

def success(data: Any, *, status_code: int = 200, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"success": True, "data": data, "error": None}
    if meta is not None:
        payload["meta"] = meta
    return payload


def error_payload(code: str, message: str, *, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "data": None, "error": error}
