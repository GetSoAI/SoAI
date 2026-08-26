"""SoAI - Multiplexed IPC worker host request replies [backend/core/ipc/multiplexed_host_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.public_projection import project_public_error
from core.ipc.multiplexed_support import MultiplexedConnection
from core.ipc.ndjson import NdjsonCodec
from core.logging.trace import get_logger
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict

__all__ = ("handle_worker_host_request",)

LOGGER_NAME = "SoAI.core.ipc.multiplexed_host_requests"
OPERATION_HOST_REQUEST_HANDLER = "core.ipc.multiplexed.host_request"
HOST_REQUEST_HANDLER_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


async def handle_worker_host_request(
    *,
    codec: NdjsonCodec,
    handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]] | None,
    connection: MultiplexedConnection,
    message: JSONDict,
) -> None:
    request_id = str(message.get("request_id") or "").strip()
    method = str(message.get("method") or "").strip()
    payload_value = message.get("payload")
    payload = payload_value if isinstance(payload_value, dict) else None
    if not request_id or not method or handler is None:
        response = _response(
            request_id=request_id or "missing",
            ok=False,
            payload={"error": "invalid_request", "message": "Host request rejected."},
        )
    elif payload is None:
        response = _response(
            request_id=request_id,
            ok=False,
            payload={
                "error": "ValidationError",
                "message": "Host request payload must be a JSON object.",
            },
        )
    else:
        response = await _call_handler(
            handler=handler,
            connection=connection,
            request_id=request_id,
            method=method,
            payload=dict(payload),
        )
    async with connection.write_lock:
        await codec.write_message(connection.writer, response, timeout_sec=LOCAL_IO_TIMEOUT_SEC)


async def _call_handler(
    *,
    handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]],
    connection: MultiplexedConnection,
    request_id: str,
    method: str,
    payload: JSONDict,
) -> JSONDict:
    try:
        payload_result = await handler(int(connection.worker_id), method, payload)
        if not isinstance(payload_result, dict):
            raise ValidationError("Host request handler returned a non-JSON payload.")
    except HOST_REQUEST_HANDLER_EXCEPTIONS as exception:
        error = coerce_to_soai_error(
            exception,
            operation=OPERATION_HOST_REQUEST_HANDLER,
            details={"worker_id": int(connection.worker_id), "method": method},
        )
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="IPC host request handler failed.",
            operation=OPERATION_HOST_REQUEST_HANDLER,
            details={"worker_id": int(connection.worker_id), "method": method},
            level="warning",
        )
        return _response(
            request_id=request_id,
            ok=False,
            payload=project_public_error(error).to_dict(),
        )
    return _response(request_id=request_id, ok=True, payload=dict(payload_result))


def _response(*, request_id: str, ok: bool, payload: JSONDict) -> JSONDict:
    return {
        "type": "response",
        "request_id": request_id,
        "ok": ok,
        "payload": dict(payload),
    }
