"""SoAI - Safe logs export failure classification [backend/app/backup/logs_export_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import sys

from core.errors.exceptions import (
    ApiError,
    ConflictError,
    InsufficientDiskSpaceError,
    NotFoundError,
    PayloadTooLargeError,
    SecurityError,
    SoAIError,
    ValidationError,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.files.managed_storage_errors import FileStorageSecurityError

__all__ = ("logs_export_failure", "project_logs_export_failure")


def logs_export_failure(code: str, status: int, message: str, cause: BaseException) -> ApiError:
    error = ApiError(message, code=code, http_status=status, operation="logs.export", cause=cause)
    apply_public_error_payload(
        error, ErrorPublicPayload(code=code, message=message, http_status=status)
    )
    return error


def project_logs_export_failure(exception: Exception) -> SoAIError:
    if isinstance(exception, ApiError | InsufficientDiskSpaceError):
        return exception
    cause: BaseException | None = exception
    while cause is not None:
        if isinstance(cause, FileNotFoundError):
            return logs_export_failure(
                "logs_export_changed",
                409,
                "Logs changed during capture. Retry the download.",
                exception,
            )
        if isinstance(cause, TimeoutError):
            return logs_export_failure(
                "logs_export_timeout",
                504,
                "Logs export timed out. Retry when the server is less busy.",
                exception,
            )
        if isinstance(cause, OSError):
            access_denied = cause.errno in {errno.EACCES, errno.EPERM}
            if sys.platform == "win32":
                access_denied = access_denied or cause.winerror in {5, 32, 33}
            if access_denied:
                return logs_export_failure(
                    "logs_export_permission",
                    403,
                    "Logs cannot be read or written. Check directory permissions and file sharing, then retry.",
                    exception,
                )
            if cause.errno == errno.ENOSPC:
                return logs_export_failure(
                    "insufficient_disk_space",
                    507,
                    "Not enough temporary disk space. Free space and retry.",
                    exception,
                )
        cause = cause.__cause__
    if isinstance(exception, ConflictError | NotFoundError | FileNotFoundError):
        return logs_export_failure(
            "logs_export_changed",
            409,
            "Logs changed during capture. Retry the download.",
            exception,
        )
    if isinstance(exception, SecurityError | FileStorageSecurityError):
        return logs_export_failure(
            "logs_export_unsafe",
            422,
            "The logs tree or temporary directory contains an unsafe path. Remove links and unsupported entries, then retry.",
            exception,
        )
    if (
        isinstance(exception, ValidationError)
        and (exception.details or {}).get("type") == "unsupported_entry"
    ):
        return logs_export_failure(
            "logs_export_unsafe",
            422,
            "The logs tree contains unsupported entries. Use only regular files and directories.",
            exception,
        )
    if isinstance(exception, ValidationError | PayloadTooLargeError):
        return logs_export_failure(
            "logs_export_limits",
            413,
            "Logs exceed archive limits or contain unsupported names. Reduce the logs tree or correct names, then retry.",
            exception,
        )
    return logs_export_failure(
        "logs_export_write",
        500,
        "The logs archive could not be written. Check temporary storage and retry.",
        exception,
    )
