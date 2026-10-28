"""SoAI - Outbound multiplexed IPC request execution [backend/core/ipc/outbound_request_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.backend_lifecycle import IpcCancellationCleanupError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    IpcRemoteRequestError,
    ServiceUnavailableError,
    SoAIError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.multiplexed_cancellation import (
    WorkerCancellationOutcome,
    build_cancel_request_id,
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
from core.timing.constants import CONTROL_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC
from core.timing.durations import seconds_to_ms
from core.timing.monotonic import monotonic_ms
from core.types.json import JSONDict, JSONValue

__all__ = ("execute_outbound_ipc_request",)

LOGGER_NAME = "SoAI.core.ipc.outbound_request_execution"
OPERATION_IPC_REQUEST_CANCEL = "core.ipc.multiplexed.request.cancel"
OPERATION_IPC_REQUEST_FAILURE = "core.ipc.multiplexed.request.failure"


@dataclass(frozen=True, slots=True)
class _CancellationTrace:
    worker_id: int
    method: str
    target_request_id: str
    started_at_ms: int = field(default_factory=monotonic_ms)

    def details(self, **fields: JSONValue) -> JSONDict:
        return {
            "worker_id": self.worker_id,
            "method": self.method,
            "target_request_id": self.target_request_id,
            "cancel_request_id": build_cancel_request_id(self.target_request_id),
            "elapsed_ms": monotonic_ms() - self.started_at_ms,
            **fields,
        }

    def record(self, transition: str, *, warning: bool = False, **fields: JSONValue) -> None:
        logger = get_logger(LOGGER_NAME)
        log = logger.warning if warning else logger.info
        log(
            "IPC cancellation %s: %s",
            transition,
            " ".join(f"{key}={value}" for key, value in self.details(**fields).items()),
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
    disconnect_on_cancel: bool = False,
    require_cancellation_completion: bool = False,
    cancellation_completion_timeout_sec: float | None = None,
    completed_result_wins_cancellation: bool = False,
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
            return await asyncio.shield(future) if require_cancellation_completion else await future
        return await asyncio.wait_for(
            asyncio.shield(future) if require_cancellation_completion else future,
            timeout=max(0.1, float(timeout_sec)),
        )
    except (asyncio.CancelledError, TimeoutError) as exception:
        trace = _CancellationTrace(int(worker_id), method_value, request_id_value)
        if require_cancellation_completion:
            settlement = create_ephemeral_task(
                _settle_cancelled_request(
                    codec,
                    connection,
                    future,
                    trace,
                    drop_connection,
                    cancellation_completion_timeout_sec,
                ),
                name="ipc-cancellation-settlement",
                log_exceptions=False,
            )
            settled = await run_idempotent_current_task_operation(
                lambda: asyncio.shield(settlement), restore_cancellation_requests=False
            )
            if isinstance(settled, IpcRemoteRequestError):
                if completed_result_wins_cancellation or isinstance(exception, TimeoutError):
                    raise settled from exception
                raise
            if completed_result_wins_cancellation and settled.get("payload") != {"cancelled": True}:
                return settled
        if isinstance(exception, asyncio.CancelledError):
            if not require_cancellation_completion:
                if disconnect_on_cancel:
                    trace.record("dropped", drop_reason="disconnect_on_cancel")
                    await drop_connection()
                else:
                    await _notify_worker_of_cancellation(
                        codec=codec,
                        connection=connection,
                        trace=trace,
                        drop_connection=drop_connection,
                    )
            raise
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
    finally:
        connection.pending.pop(request_id_value, None)
        connection.event_handlers.pop(request_id_value, None)


async def _settle_cancelled_request(
    codec: NdjsonCodec,
    connection: MultiplexedConnection,
    future: asyncio.Future[JSONDict],
    trace: _CancellationTrace,
    drop_connection: Callable[[], Awaitable[None]],
    completion_timeout_sec: float | None,
) -> JSONDict | IpcRemoteRequestError:
    timeout_sec = CONTROL_TIMEOUT_SEC if completion_timeout_sec is None else completion_timeout_sec
    settlement_deadline_ms = seconds_to_ms(timeout_sec)
    try:
        if not future.done():
            await _notify_worker_of_cancellation(
                codec=codec,
                connection=connection,
                trace=trace,
                drop_connection=drop_connection,
            )
        async with asyncio.timeout(timeout_sec):
            response = await asyncio.shield(future)
    except IpcRemoteRequestError as exception:
        if exception.code == IpcCancellationCleanupError.code:
            await drop_connection()
            raise IpcCancellationCleanupError(
                "IPC worker cancellation cleanup failed.",
                details=trace.details(settlement="remote_cleanup_failed"),
                cause=exception,
            ) from exception
        trace.record(
            "settled", settlement="remote_error", settlement_deadline_ms=settlement_deadline_ms
        )
        return exception
    except (SoAIError, OSError) as exception:
        failure: JSONDict = {
            "settlement": _classify_settlement_failure(exception),
            "settlement_deadline_ms": settlement_deadline_ms,
            "drop_reason": "cancellation_settlement_failed",
        }
        trace.record("settlement_failed", warning=True, **failure)
        await drop_connection()
        raise IpcCancellationCleanupError(
            "IPC worker cancellation cleanup did not settle.",
            details=trace.details(**failure),
            cause=exception,
        ) from exception
    trace.record("settled", settlement="completed", settlement_deadline_ms=settlement_deadline_ms)
    return response


def _classify_settlement_failure(exception: BaseException) -> str:
    if isinstance(exception, TimeoutError):
        return "timeout"
    if isinstance(exception, ServiceUnavailableError):
        return "connection_closed"
    return "transport_error"


async def _notify_worker_of_cancellation(
    *,
    codec: NdjsonCodec,
    connection: MultiplexedConnection,
    trace: _CancellationTrace,
    drop_connection: Callable[[], Awaitable[None]],
) -> None:
    trace.record(
        "requested",
        acknowledgement_deadline_ms=seconds_to_ms(LOCAL_IO_TIMEOUT_SEC),
    )
    try:
        outcome = await cancel_worker_call(
            codec=codec,
            connection=connection,
            target_request_id=trace.target_request_id,
            timeout_sec=LOCAL_IO_TIMEOUT_SEC,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to deliver IPC cancellation to worker; dropping connection.",
            operation=OPERATION_IPC_REQUEST_CANCEL,
            details=trace.details(
                drop_reason=(
                    "connection_closed"
                    if isinstance(exception, ServiceUnavailableError)
                    else "cancellation_delivery_failed"
                )
            ),
            level="warning",
        )
        await drop_connection()
        return
    trace.record(outcome.value, warning=outcome is not WorkerCancellationOutcome.ACKNOWLEDGED)


def _log_ipc_request_failure(exception: BaseException, *, worker_id: int, method: str) -> None:
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message="IPC request failed; dropping worker connection.",
        operation=OPERATION_IPC_REQUEST_FAILURE,
        details={"worker_id": int(worker_id), "method": method},
        level="warning",
    )
