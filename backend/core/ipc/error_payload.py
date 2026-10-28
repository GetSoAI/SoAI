"""SoAI - Structured error payloads for trusted IPC peers [backend/core/ipc/error_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import IpcRemoteRequestError, ValidationError
from core.ipc.remote_error_metadata import (
    REMOTE_ERROR_CODE_KEY,
    REMOTE_ERROR_PARAM_KEY,
    REMOTE_ERROR_TRACE_ID_KEY,
)
from core.validation.strict_numbers import require_int_in_range_strict

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_ipc_error_payload", "decode_ipc_error_payload")


def build_ipc_error_payload(error: SoAIError) -> JSONDict:
    payload: JSONDict = {
        "code": error.code,
        "message": error.message,
        "http_status": error.http_status,
    }
    if error.details:
        payload["details"] = dict(error.details)
    if error.trace_id:
        payload["trace_id"] = error.trace_id
    if error.public_message is not None:
        payload["public_message"] = error.public_message
        if error.public_param is not None:
            payload["param"] = error.public_param
        if error.public_details is not None:
            payload["public_details"] = dict(error.public_details)
    return payload


def decode_ipc_error_payload(
    payload_value: JSONValue,
    *,
    operation: str,
    worker_id: int | None = None,
) -> IpcRemoteRequestError:
    if (
        isinstance(payload_value, dict)
        and any(key in payload_value for key in ("public_message", "public_details"))
        and "http_status" not in payload_value
    ):
        raise ValidationError("Typed IPC errors require an HTTP status.")
    if isinstance(payload_value, dict):
        message_value = payload_value.get("message")
        details = _build_remote_error_details(payload_value, worker_id=worker_id)
    else:
        message_value = None
        details = {"worker_id": worker_id} if worker_id is not None else {}
    error_message = (
        message_value
        if isinstance(message_value, str) and message_value
        else "IPC worker request failed."
    )
    error = IpcRemoteRequestError(
        error_message,
        operation=operation,
        details=details,
    )
    if isinstance(payload_value, dict) and "http_status" in payload_value:
        status_code = require_int_in_range_strict(
            payload_value["http_status"],
            minimum=400,
            maximum=599,
            error_message="IPC error HTTP status must be an integer from 400 through 599.",
        )
        if (
            "details" in payload_value
            and payload_value["details"] is not None
            and not isinstance(payload_value["details"], dict)
        ):
            raise ValidationError("IPC error details must be a JSON object.")
        code = payload_value.get("code")
        if (
            not isinstance(code, str | int)
            or isinstance(code, bool)
            or (isinstance(code, str) and not code.strip())
        ):
            raise ValidationError("IPC error code must be a non-empty string or integer.")
        error.code = code
        error.http_status = status_code
        trace_id = payload_value.get("trace_id")
        if trace_id is not None and (not isinstance(trace_id, str) or not trace_id.strip()):
            raise ValidationError("IPC error trace identity must be a non-empty string.")
        error.trace_id = trace_id
        if "public_message" not in payload_value and any(
            key in payload_value for key in ("public_details", "param")
        ):
            raise ValidationError("IPC public error metadata requires public guidance.")
        if "public_message" in payload_value:
            public_message = payload_value["public_message"]
            if not isinstance(public_message, str) or not public_message.strip():
                raise ValidationError("IPC public error guidance must be a non-empty string.")
            public_details = payload_value.get("public_details")
            if public_details is not None and not isinstance(public_details, dict):
                raise ValidationError("IPC public error details must be a JSON object.")
            public_param = payload_value.get("param")
            if public_param is not None and (
                not isinstance(public_param, str) or not public_param.strip()
            ):
                raise ValidationError("IPC public error parameter must be a non-empty string.")
            error.public_message = public_message
            error.public_param = public_param
            error.public_details = public_details
    return error


def _build_remote_error_details(payload: JSONDict, *, worker_id: int | None) -> JSONDict:
    details_value = payload.get("details")
    details = dict(details_value) if isinstance(details_value, dict) else dict(payload)
    if worker_id is not None:
        details["worker_id"] = worker_id
    _copy_remote_error_text_field(
        payload,
        source_key="code",
        target_key=REMOTE_ERROR_CODE_KEY,
        details=details,
    )
    _copy_remote_error_text_field(
        payload,
        source_key="param",
        target_key=REMOTE_ERROR_PARAM_KEY,
        details=details,
    )
    _copy_remote_error_text_field(
        payload,
        source_key="trace_id",
        target_key=REMOTE_ERROR_TRACE_ID_KEY,
        details=details,
    )
    return details


def _copy_remote_error_text_field(
    payload: JSONDict,
    *,
    source_key: str,
    target_key: str,
    details: JSONDict,
) -> None:
    source_value = payload.get(source_key)
    if not isinstance(source_value, str):
        return
    normalized_value = source_value.strip()
    if not normalized_value:
        return
    details[target_key] = normalized_value
