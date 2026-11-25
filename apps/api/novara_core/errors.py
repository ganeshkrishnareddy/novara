"""Sanitised validation-error responses.

Pydantic includes the offending ``input`` value in 422 responses. For endpoints
that accept configuration dictionaries this can echo a submitted secret back to
the caller and into access logs. This handler keeps the actionable fields
(``loc``, ``msg``, ``type``) and drops raw input and context everywhere.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def install_safe_validation_errors(app: FastAPI) -> None:
    """Install a 422 handler that never reflects submitted values."""

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        clean_errors = []
        for error in exc.errors():
            clean_errors.append(
                {
                    key: value
                    for key, value in error.items()
                    if key not in {"input", "ctx"}
                }
            )
        return JSONResponse(status_code=422, content={"detail": clean_errors})
