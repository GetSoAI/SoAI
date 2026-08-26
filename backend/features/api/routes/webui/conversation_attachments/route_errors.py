"""SoAI - WebUI conversation attachment route error mapping [backend/features/api/routes/webui/conversation_attachments/route_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from fastapi import Request

from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ConflictError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    ValidationError,
)
from core.files.managed_storage_errors import FileStorageSecurityError
from core.logging.trace import get_logger
from features.api.runtime.context import get_request_trace_id, raise_api_error
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_server_error,
)
from features.api.runtime.upload_error_resolution import resolve_upload_api_error

__all__ = ("raise_attachment_route_error",)

LOGGER_NAME = "SoAI.features.api.route_errors"
OPERATION_WEBUI_ATTACHMENT_ROUTE = "webui.conversation_attachments.route"


def raise_attachment_route_error(
    request: Request,
    exception: Exception,
    *,
    already_logged: bool = False,
) -> NoReturn:
    if isinstance(exception, ConflictError):
        raise_conflict(request, str(exception))
    if isinstance(exception, ValidationError):
        raise_invalid_request(request, str(exception))
    if isinstance(exception, InsufficientDiskSpaceError | PayloadTooLargeError):
        status_code, error_type, message, detail_message, headers = resolve_upload_api_error(
            exception,
            default_server_message="Attachment upload failed.",
        )
        _ = detail_message
        raise_api_error(
            request,
            status_code,
            error_type,
            message,
            headers=dict(headers) if headers is not None else None,
        )
    if isinstance(exception, FileStorageSecurityError):
        raise_conflict(request, str(exception))
    trace_id = get_request_trace_id(request)
    if not already_logged:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Conversation attachment route failed.",
            operation=OPERATION_WEBUI_ATTACHMENT_ROUTE,
            trace_id=trace_id,
        )
    raise_server_error(request, "Attachment operation failed.", extra={"trace_id": trace_id})
