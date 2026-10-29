"""API error model. Codes match `src/domain/errors.ts` APP_ERROR_CODES in the frontend."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("omniora.errors")

ErrorCode = Literal[
    "validation",
    "not-found",
    "read-only",
    "provider-not-configured",
    "invalid-credentials",
    "email-in-use",
    "unauthenticated",
    "forbidden",
    "conflict",
    "rate-limited",
    "network",
    "unexpected",
]

STATUS_BY_CODE: dict[ErrorCode, int] = {
    "validation": 422,
    "not-found": 404,
    "read-only": 403,
    "provider-not-configured": 503,
    "invalid-credentials": 401,
    "email-in-use": 409,
    "unauthenticated": 401,
    "forbidden": 403,
    "conflict": 409,
    "rate-limited": 429,
    "network": 502,
    "unexpected": 500,
}


class ApiError(Exception):
    """Raised by services. `message` and `details` must be safe to show to end users."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: list[str] | None = None,
        status: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.details = details or []
        self.status = status or STATUS_BY_CODE[code]
        self.headers = headers


def error_body(code: str, message: str, details: list[str] | None = None) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations and messages only; never echo submitted values back.
        details = []
        for error in exc.errors()[:20]:
            location = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path"))
            details.append(f"{location}: {error.get('msg', 'invalid')}" if location else str(error.get("msg")))
        return JSONResponse(error_body("validation", "The request is not valid.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return JSONResponse(error_body("not-found", "Not found."), status_code=404)
        if exc.status_code == 405:
            return JSONResponse(error_body("validation", "Method not allowed."), status_code=405)
        return JSONResponse(
            error_body("unexpected", "The request could not be completed."), status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"error_type": type(exc).__name__})
        return JSONResponse(error_body("unexpected", "Something went wrong. Please try again."), status_code=500)
