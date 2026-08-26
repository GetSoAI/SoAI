"""SoAI - Multiplexed IPC inbound message dispatch [backend/core/ipc/multiplexed_message_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import IpcRemoteRequestError, ValidationError
from core.ipc.multiplexed_host_requests import (
    handle_worker_host_request,
)
from core.ipc.multiplexed_support import MultiplexedConnection
from core.ipc.ndjson import NdjsonCodec
from core.ipc.remote_error_metadata import (
    REMOTE_ERROR_CODE_KEY,
    REMOTE_ERROR_PARAM_KEY,
    REMOTE_ERROR_TRACE_ID_KEY,
)
from core.types.json import JSONDict

__all__ = ("dispatch_ipc_message",)


async def dispatch_ipc_message(
    *,
    codec: NdjsonCodec,
    host_request_handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]] | None,
    connection: MultiplexedConnection,
    message: JSONDict,
) -> None:
    message_type = str(message.get("type") or "")
    request_id = str(message.get("request_id") or "")
    if not message_type:
        raise ValidationError("IPC message type is required.")
    if message_type == "response":
        _handle_response(connection, request_id, message)
        return
    if message_type == "request":
        await _handle_host_request(
            codec=codec,
            host_request_handler=host_request_handler,
            connection=connection,
            request_id=request_id,
            message=message,
        )
        return
    await _handle_event(connection, request_id, message_type, message)


def _handle_response(
    connection: MultiplexedConnection,
    request_id: str,
    message: JSONDict,
) -> None:
    if not request_id:
        raise ValidationError("IPC response request_id is required.")
    pending = connection.pending.get(request_id)
    if pending is None or pending.done():
        return
    ok_value = message.get("ok", True)
    if not isinstance(ok_value, bool):
        raise ValidationError("IPC response ok flag must be a boolean.")
    if ok_value:
        pending.set_result(message)
        return
    payload_value = message.get("payload")
    if isinstance(payload_value, dict):
        message_value = payload_value.get("message")
        details = _build_remote_error_details(payload_value, worker_id=int(connection.worker_id))
    else:
        message_value = None
        details = {"worker_id": int(connection.worker_id)}
    error_message = (
        message_value
        if isinstance(message_value, str) and message_value
        else "IPC worker request failed."
    )
    pending.set_exception(
        IpcRemoteRequestError(
            error_message,
            operation="core.ipc.multiplexed.response.error",
            details=details,
        ),
    )


def _build_remote_error_details(payload: JSONDict, *, worker_id: int) -> JSONDict:
    details_value = payload.get("details")
    details = dict(details_value) if isinstance(details_value, dict) else dict(payload)
    details["worker_id"] = int(worker_id)
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


async def _handle_host_request(
    *,
    codec: NdjsonCodec,
    host_request_handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]] | None,
    connection: MultiplexedConnection,
    request_id: str,
    message: JSONDict,
) -> None:
    if not request_id:
        raise ValidationError("IPC request_id is required.")
    await handle_worker_host_request(
        codec=codec,
        handler=host_request_handler,
        connection=connection,
        message=message,
    )


async def _handle_event(
    connection: MultiplexedConnection,
    request_id: str,
    message_type: str,
    message: JSONDict,
) -> None:
    handler = connection.event_handlers.get(request_id)
    if handler is not None and message_type.startswith("event."):
        await handler(message)
        return
    raise ValidationError(f"Unsupported IPC message type '{message_type}'.")
