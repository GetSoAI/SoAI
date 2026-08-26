"""SoAI - Outbound multiplexed IPC request execution [backend/core/ipc/outbound_request_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.multiplexed_cancellation import (
    WorkerCancellationOutcome,
    cancel_worker_call,
)
from core.ipc.multiplexed_request_errors import (
    raise_ipc_request_failure,
    raise_ipc_request_timeout,
)
from core.ipc.multiplexed_requests import (
    build_ipc_request_message,
    write_ipc_request_message_bytes,
)
from core.ipc.multiplexed_support import (
    MultiplexedConnection,
    require_ipc_text,
)
from core.ipc.ndjson import NdjsonCodec
from core.ipc.outbound_encoding import encode_outbound_ipc_message
from core.logging.trace import get_logger
from core.types.json import JSONDict

__all__ = ("execute_outbound_ipc_request",)

LOGGER_NAME = "SoAI.core.ipc.outbound_request_execution"
OPERATION_IPC_REQUEST_CANCEL = "core.ipc.multiplexed.request.cancel"
OPERATION_IPC_REQUEST_FAILURE = "core.ipc.multiplexed.request.failure"
IPC_REQUEST_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ServiceUnavailableError,
    TimeoutError,
)


async def execute_outbound_ipc_request(
    *,
    encoding_pool: BoundedBlockingPool,
    codec: NdjsonCodec,
    connection: MultiplexedConnection,
    worker_id: int,
    method: str,
    request_id: str,
    payload: JSONDict,
    timeout_sec: float | None,
    event_handler: Callable[[JSONDict], Awaitable[None]] | None,
    drop_connection: Callable[[], Awaitable[None]],
) -> JSONDict:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[JSONDict] = loop.create_future()
    request_id_value = require_ipc_text(request_id, "request_id")
    method_value = require_ipc_text(method, "method")
    request_message = build_ipc_request_message(
        method=method_value,
        request_id=request_id_value,
        payload=payload,
    )
    request_bytes = await encode_outbound_ipc_message(
        encoding_pool,
        request_message,
        max_bytes=codec.max_line_bytes,
        details={"worker_id": int(worker_id), "method": method_value},
        operation="core.ipc.multiplexed.request.oversized",
    )
    connection.pending[request_id_value] = future
    if event_handler is not None:
        connection.event_handlers[request_id_value] = event_handler
    try:
        await write_ipc_request_message_bytes(
            connection=connection,
            data=request_bytes,
            timeout_sec=5.0,
        )
        if timeout_sec is None:
            return await future
        return await asyncio.wait_for(future, timeout=max(0.1, float(timeout_sec)))
    except asyncio.CancelledError:
        await _notify_worker_of_cancellation(
            codec=codec,
            connection=connection,
            request_id=request_id_value,
            worker_id=int(worker_id),
            method=method_value,
            drop_connection=drop_connection,
        )
        raise
    except TimeoutError as exception:
        await drop_connection()
        raise_ipc_request_timeout(
            exception,
            worker_id=int(worker_id),
            method=method_value,
        )
    except OSError as exception:
        await drop_connection()
        _log_ipc_request_failure(exception, worker_id=int(worker_id), method=method_value)
        raise_ipc_request_failure(
            exception,
            worker_id=int(worker_id),
            method=method_value,
        )
    except ServiceUnavailableError as exception:
        await drop_connection()
        raise_ipc_request_failure(
            exception,
            worker_id=int(worker_id),
            method=method_value,
        )
    except IPC_REQUEST_FAILURE_EXCEPTIONS as exception:
        await drop_connection()
        _log_ipc_request_failure(exception, worker_id=int(worker_id), method=method_value)
        raise_ipc_request_failure(
            exception,
            worker_id=int(worker_id),
            method=method_value,
        )
    finally:
        connection.pending.pop(request_id_value, None)
        connection.event_handlers.pop(request_id_value, None)


async def _notify_worker_of_cancellation(
    *,
    codec: NdjsonCodec,
    connection: MultiplexedConnection,
    request_id: str,
    worker_id: int,
    method: str,
    drop_connection: Callable[[], Awaitable[None]],
) -> None:
    try:
        outcome = await cancel_worker_call(
            codec=codec,
            connection=connection,
            target_request_id=request_id,
            timeout_sec=5.0,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to deliver IPC cancellation to worker; dropping connection.",
            operation=OPERATION_IPC_REQUEST_CANCEL,
            details={"worker_id": worker_id, "method": method},
            level="warning",
        )
        await drop_connection()
        return
    if outcome is WorkerCancellationOutcome.ACKNOWLEDGED:
        return
    get_logger(LOGGER_NAME).warning(
        "IPC worker did not confirm cancellation (%s); keeping the connection. worker_id=%d method=%s",
        outcome.value,
        worker_id,
        method,
    )


def _log_ipc_request_failure(exception: BaseException, *, worker_id: int, method: str) -> None:
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message="IPC request failed; dropping worker connection.",
        operation=OPERATION_IPC_REQUEST_FAILURE,
        details={"worker_id": int(worker_id), "method": method},
        level="warning",
    )
