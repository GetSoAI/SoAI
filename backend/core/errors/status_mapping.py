"""SoAI - Error type to HTTP status code mapping [backend/core/errors/status_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType

__all__ = ("error_type_to_status_code",)


def error_type_to_status_code(error_type: ErrorType) -> int:
    match error_type:
        case ErrorType.NOT_FOUND:
            return 404
        case ErrorType.INVALID_REQUEST:
            return 422
        case ErrorType.MODEL_OUTPUT_CONTRACT:
            return 502
        case ErrorType.MODEL_STOPPED | ErrorType.MODEL_DELETED:
            return 409
        case ErrorType.AUTHENTICATION_ERROR:
            return 401
        case ErrorType.FORBIDDEN:
            return 403
        case ErrorType.SERVICE_UNAVAILABLE:
            return 503
        case ErrorType.OVERLOADED:
            return 503
        case ErrorType.TIMEOUT_ERROR:
            return 504
        case ErrorType.PLUGIN_UNAVAILABLE:
            return 503
        case ErrorType.PLUGIN_QUARANTINED:
            return 503
        case ErrorType.PLUGIN_DISABLED:
            return 503
        case ErrorType.PLUGIN_INITIALIZING:
            return 503
        case ErrorType.CONFLICT:
            return 409
        case ErrorType.RATE_LIMIT:
            return 429
        case ErrorType.LOCKED:
            return 423
        case ErrorType.ACTION_NOT_SUPPORTED:
            return 400
        case ErrorType.ACCELERATOR_MEMORY_EXHAUSTED | ErrorType.SYSTEM_MEMORY_EXHAUSTED:
            return 507
        case _:
            return 500
