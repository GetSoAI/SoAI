"""SoAI - Multiplexed IPC inbound message dispatch [backend/core/ipc/multiplexed_message_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.ipc.error_payload import decode_ipc_error_payload
from core.ipc.multiplexed_host_requests import (
    handle_worker_host_request,
)
from core.ipc.multiplexed_support import MultiplexedConnection
from core.ipc.ndjson import NdjsonCodec
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
        invalid_flag = ValidationError("IPC response ok flag must be a boolean.")
        pending.set_exception(invalid_flag)
        raise invalid_flag
    if ok_value:
        pending.set_result(message)
        return
    try:
        error = decode_ipc_error_payload(
            message.get("payload"),
            operation="core.ipc.multiplexed.response.error",
            worker_id=int(connection.worker_id),
        )
    except ValidationError as exception:
        pending.set_exception(exception)
        raise
    pending.set_exception(error)


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
