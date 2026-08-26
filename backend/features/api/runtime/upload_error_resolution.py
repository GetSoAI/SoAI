"""SoAI - Shared upload error to API response resolution [backend/features/api/runtime/upload_error_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    RateLimitError,
    ValidationError,
)

__all__ = ("resolve_upload_api_error",)


def resolve_upload_api_error(
    exception: Exception,
    *,
    default_server_message: str,
) -> tuple[int, str, str, str | None, Mapping[str, str] | None]:
    if isinstance(exception, InsufficientDiskSpaceError):
        return exception.http_status, str(exception.code), str(exception.message), None, None
    if isinstance(exception, PayloadTooLargeError):
        return exception.http_status, str(exception.code), str(exception.message), None, None
    if isinstance(exception, RateLimitError):
        message = str(exception.message)
        return exception.http_status, str(exception.code), message, message, exception.headers
    if isinstance(exception, ValidationError):
        message = str(exception.message)
        return 400, str(exception.code), message, message, None
    return 500, "server_error", default_server_message, None, None
