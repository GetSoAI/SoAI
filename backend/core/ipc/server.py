"""SoAI - Local IPC server for managed workers [backend/core/ipc/server.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.loopback_server_base import LoopbackIpcServerBase
from core.ipc.ndjson import IpcStreamClosedError, NdjsonCodec
from core.ipc.server_connections import WorkerConnection, WorkerConnectionIndex
from core.ipc.stream_closing import close_ipc_writer
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("LocalIpcServer",)

LOGGER_NAME = "SoAI.core.ipc.server"
OPERATION_CORE_IPC_SERVER_HANDLE_CONNECTION = "core.ipc.server.handle_connection"
OPERATION_CORE_IPC_SERVER_REQUEST_CONNECTION_ERROR = "core.ipc.server.request.connection_error"


WORKER_CONNECT_POLL_INTERVAL_SEC = 0.05
IPC_REQUEST_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    IpcStreamClosedError,
    UnicodeError,
)
IPC_CONNECTION_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    IpcStreamClosedError,
    ConnectionError,
    OSError,
    UnicodeError,
)


class LocalIpcServer(LoopbackIpcServerBase):
    def __init__(self, *, codec: NdjsonCodec | None = None) -> None:
        super().__init__(codec=codec or NdjsonCodec())
        self._connections = WorkerConnectionIndex()

    async def shutdown(self) -> None:
        await self._connections.close_all()
        await self._shutdown_server()

    async def wait_for_worker(self, worker_id: int, *, timeout_sec: float) -> None:
        deadline = asyncio.get_running_loop().time() + max(0.0, float(timeout_sec))
        while True:
            connection = await self._connections.get(worker_id)
            if connection is not None:
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise ServiceUnavailableError(
                    "IPC worker failed to connect.",
                    operation="core.ipc.server.wait_for_worker",
                    details={"worker_id": int(worker_id)},
                )
            await asyncio.sleep(WORKER_CONNECT_POLL_INTERVAL_SEC)

    async def request(
        self,
        worker_id: int,
        *,
        method: str,
        request_id: str,
        payload: JSONDict,
        timeout_sec: float,
    ) -> JSONDict:
        logger = get_logger(LOGGER_NAME)
        method_value = str(method or "").strip()
        if not method_value:
            raise ValidationError("method is required for IPC request.")
        request_id_value = str(request_id or "").strip()
        if not request_id_value:
            raise ValidationError("request_id is required for IPC request.")
        connection = await self._connections.get(int(worker_id))
        if connection is None:
            raise ServiceUnavailableError(
                "IPC worker is not connected.",
                operation="core.ipc.server.request.no_worker",
                details={"worker_id": int(worker_id)},
            )
        message: JSONDict = {
            "type": "request",
            "request_id": request_id_value,
            "method": method_value,
            "payload": dict(payload or {}),
        }
        timeout_value = max(0.1, float(timeout_sec))
        async with connection.lock:
            try:
                await self._codec.write_message(
                    connection.writer,
                    message,
                    timeout_sec=timeout_value,
                )
                response = await self._codec.read_message(
                    connection.reader,
                    timeout_sec=timeout_value,
                )
            except TimeoutError as exception:
                await self._drop_connection(worker_id, writer=connection.writer)
                raise ServiceUnavailableError(
                    "IPC request timed out.",
                    operation="core.ipc.server.request.timeout",
                    details={"worker_id": int(worker_id), "method": method_value},
                    cause=exception,
                ) from exception
            except IPC_REQUEST_RECOVERABLE_EXCEPTIONS as exception:
                await self._drop_connection(worker_id, writer=connection.writer)
                error = coerce_to_soai_error(
                    exception,
                    operation="core.ipc.server.request.connection_error",
                    details={"worker_id": int(worker_id), "method": method_value},
                )
                log_exception(
                    logger,
                    error,
                    message="IPC request failed due to connection error.",
                    operation=OPERATION_CORE_IPC_SERVER_REQUEST_CONNECTION_ERROR,
                    details={"worker_id": int(worker_id), "method": method_value},
                    level="warning",
                )
                raise ServiceUnavailableError(
                    "IPC request failed due to connection error.",
                    operation="core.ipc.server.request.connection_error",
                    details={"worker_id": int(worker_id), "method": method_value},
                    cause=exception,
                ) from exception
        await self._validate_response(
            worker_id=int(worker_id),
            writer=connection.writer,
            response=response,
            request_id=request_id_value,
        )
        return response

    async def _validate_response(
        self,
        *,
        worker_id: int,
        writer: asyncio.StreamWriter,
        response: JSONDict,
        request_id: str,
    ) -> None:
        if response.get("type") != "response":
            await self._drop_connection(worker_id, writer=writer)
            raise ValidationError("IPC response has invalid type.")
        if response.get("request_id") != request_id:
            await self._drop_connection(worker_id, writer=writer)
            raise ValidationError("IPC response request_id mismatch.")

    async def _drop_connection(
        self,
        worker_id: int,
        *,
        writer: asyncio.StreamWriter | None = None,
    ) -> None:
        existing = await self._connections.drop(worker_id, writer=writer)
        if existing is None:
            return
        await close_ipc_writer(existing.writer, worker_id=int(worker_id))

    @override
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        worker_id: int | None = None
        try:
            hello = await self._codec.read_message(reader, timeout_sec=5.0)
            if hello.get("type") != "hello":
                raise ValidationError("IPC hello message type mismatch.")
            if str(hello.get("token") or "") != self._token:
                raise ValidationError("IPC token mismatch.")
            worker_id_raw = hello.get("worker_id")
            if not isinstance(worker_id_raw, int):
                raise ValidationError("IPC worker_id must be an integer.")
            worker_id = int(worker_id_raw)
            connection = WorkerConnection(
                worker_id=worker_id,
                reader=reader,
                writer=writer,
                lock=asyncio.Lock(),
            )
            old = await self._connections.replace(connection)
            if old is not None:
                await close_ipc_writer(old.writer, worker_id=int(worker_id))
            await self._codec.write_message(writer, {"type": "hello_ack"}, timeout_sec=5.0)
            await writer.wait_closed()
        except IPC_CONNECTION_RECOVERABLE_EXCEPTIONS as exception:
            peer = writer.get_extra_info("peername")
            error = coerce_to_soai_error(
                exception,
                operation="core.ipc.server.handle_connection",
                details={
                    "peer": str(peer),
                    "worker_id": int(worker_id) if worker_id is not None else None,
                },
            )
            log_handled_exception(
                logger,
                error,
                message="IPC connection handler failed (non-critical).",
                operation=OPERATION_CORE_IPC_SERVER_HANDLE_CONNECTION,
                details={
                    "peer": str(peer),
                    "worker_id": int(worker_id) if worker_id is not None else None,
                },
                level="debug",
            )
            await close_ipc_writer(writer, worker_id=None, details={"peer": str(peer)})
            return
        finally:
            if worker_id is not None:
                await self._connections.drop_if_matches(worker_id, writer=writer)
