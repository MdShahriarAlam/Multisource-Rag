"""Typed exception hierarchy + FastAPI exception handlers."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class RAGError(Exception):
    """Base exception. Subclasses map to HTTP status codes via handler."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidInput(RAGError):
    status_code = 400
    error_code = "invalid_input"


class InvalidQuery(RAGError):
    status_code = 400
    error_code = "invalid_query"


class UnsafeQuery(RAGError):
    """SQL rejected by safety guard."""

    status_code = 400
    error_code = "unsafe_query"


class PathTraversal(RAGError):
    status_code = 400
    error_code = "path_traversal"


class SourceNotFound(RAGError):
    status_code = 404
    error_code = "source_not_found"


class FileNotFound(RAGError):
    status_code = 404
    error_code = "file_not_found"


class SourceUnavailable(RAGError):
    status_code = 503
    error_code = "source_unavailable"


class IngestionError(RAGError):
    status_code = 500
    error_code = "ingestion_error"


class EmbeddingError(RAGError):
    status_code = 503
    error_code = "embedding_error"


class TimeoutExceeded(RAGError):
    status_code = 504
    error_code = "timeout"


class NotInitialized(RAGError):
    status_code = 503
    error_code = "not_initialized"


def rag_error_handler(request: Request, exc: RAGError) -> JSONResponse:
    """FastAPI handler: structured JSON error responses."""
    log.warning(
        "RAGError %s on %s %s: %s",
        exc.error_code,
        request.method,
        request.url.path,
        exc.message,
        extra={"details": exc.details},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler — never leak stack traces."""
    log.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        },
    )
