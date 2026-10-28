"""SoAI - Safe filesystem operation failure causes [backend/core/filesystem/operation_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import sys

from core.errors.external_service_exception import ExternalServiceError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload

__all__ = ("build_filesystem_operation_error",)


def _windows_error_code(exception: OSError) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        native_code = exception.winerror
    except AttributeError:
        native_code = None
    return native_code


def build_filesystem_operation_error(
    exception: OSError, *, reference: str | None = None
) -> ExternalServiceError:
    windows_error = _windows_error_code(exception)
    if windows_error in (32, 33):
        code, status = "file_in_use", 423
        message = "Another program is using the files. Close that program or wait for it to release them, then retry."
    elif windows_error in (39, 112) or exception.errno == errno.ENOSPC:
        code, status = "insufficient_disk_space", 507
        message = "There is not enough free disk space. Free up space and retry."
    elif windows_error == 5 or isinstance(exception, PermissionError):
        code, status = "file_access_denied", 403
        message = "Access to the files was denied. Check folder permissions and any security software that blocks access, then retry."
    else:
        code, status = "file_operation_failed", 500
        message = "The file operation could not finish. Review the operation diagnostics and retry."
    error = ExternalServiceError(message, cause=exception, trace_id=reference)
    apply_public_error_payload(
        error,
        ErrorPublicPayload(code=code, message=message, http_status=status, trace_id=reference),
    )
    return error
