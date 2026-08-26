"""SoAI - Exception coercion into typed SoAI errors [backend/core/errors/exception_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.messages import resolve_error_message, resolve_exception_error_message

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("coerce_to_soai_error",)


def coerce_to_soai_error(
    exception: BaseException,
    *,
    message: str | None = None,
    code: str | None = None,
    http_status: int | None = None,
    details: Mapping[str, JSONValue] | None = None,
    operation: str | None = None,
    trace_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> SoAIError:
    if not isinstance(exception, SoAIError):
        default_message = resolve_exception_error_message(exception)
        resolved_message = (
            resolve_error_message(message, default_message=default_message)
            if message is not None
            else default_message
        )
        error = SoAIError(
            resolved_message,
            details=details,
            operation=operation,
            cause=exception,
            trace_id=trace_id,
            headers=headers,
        )
        if code:
            error.code = code
        if http_status:
            error.http_status = http_status
        return error
    if message is not None:
        resolved_message = resolve_error_message(message, default_message=exception.message)
        exception.message = resolved_message
        exception.args = (resolved_message,)
    if code is not None:
        exception.code = code
    if http_status is not None:
        exception.http_status = http_status
    if details is not None:
        merged_details = dict(exception.details) if exception.details else {}
        merged_details.update(details)
        exception.details = merged_details or None
    if operation is not None:
        exception.operation = operation
    if trace_id is not None:
        exception.trace_id = trace_id
    if headers is not None:
        merged_headers = dict(exception.headers) if exception.headers else {}
        merged_headers.update(headers)
        exception.headers = merged_headers or None
    return exception
