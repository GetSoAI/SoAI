"""SoAI - Multiplexed NDJSON IPC bridge [backend/core/ipc/multiplexed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import override

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    shutdown_bounded_pool_executor,
)
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.loopback_server_base import LoopbackIpcServerBase
from core.ipc.multiplexed_connection_reader import read_multiplexed_connection
from core.ipc.multiplexed_support import (
    MultiplexedConnection,
    close_connection,
    fail_pending,
    validate_hello,
)
from core.ipc.multiplexed_worker_authorization import MultiplexedWorkerAuthorization
from core.ipc.ndjson import IpcStreamClosedError, NdjsonCodec
from core.ipc.outbound_request_execution import execute_outbound_ipc_request
from core.ipc.stream_closing import close_ipc_writer, is_ipc_peer_closed_exception
from core.logging.trace import get_logger
from core.types.json import JSONDict

__all__ = ("MultiplexedIpcServer",)

LOGGER_NAME = "SoAI.core.ipc.multiplexed"
OPERATION_IPC_CONNECTION_FAILURE = "core.ipc.multiplexed.connection"
WORKER_CONNECT_POLL_INTERVAL_SEC = 0.05
IPC_CONNECTION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    IpcStreamClosedError,
    ConnectionError,
    OSError,
)


class MultiplexedIpcServer(LoopbackIpcServerBase):
    def __init__(
        self,
        *,
        encoding_pool: BoundedBlockingPool,
        codec: NdjsonCodec | None = None,
        host_request_handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]] | None = None,
    ) -> None:
        super().__init__(codec=codec or NdjsonCodec())
        self._encoding_pool = encoding_pool
        self._host_request_handler = host_request_handler
        self._connections: dict[int, MultiplexedConnection] = {}
        self._authorization = MultiplexedWorkerAuthorization()
        self._lock = asyncio.Lock()

    @property
    def max_request_bytes(self) -> int:
        return self.max_message_bytes

    async def shutdown(self) -> None:
        try:
            await self._shutdown_server()
            async with self._lock:
                connections = list(self._connections.values())
                self._connections.clear()
            await self._authorization.clear()
            for connection in connections:
                await close_connection(connection)
        finally:
            shutdown_bounded_pool_executor(self._encoding_pool)

    async def expect_worker_secret(self, worker_id: int, *, worker_secret: str) -> None:
        await self._authorization.expect_worker_secret(worker_id, worker_secret=worker_secret)

    async def forget_worker_secret(self, worker_id: int) -> None:
        await self._authorization.forget_worker_secret(worker_id)

    async def disconnect_worker(self, worker_id: int) -> None:
        async with self._lock:
            connection = self._connections.pop(int(worker_id), None)
        if connection is not None:
            await close_connection(connection)

    async def wait_for_worker(self, worker_id: int, *, timeout_sec: float) -> None:
        deadline = asyncio.get_running_loop().time() + max(0.0, float(timeout_sec))
        while True:
            async with self._lock:
                if int(worker_id) in self._connections:
                    return
            if asyncio.get_running_loop().time() >= deadline:
                raise ServiceUnavailableError(
                    "IPC worker failed to connect.",
                    operation="core.ipc.multiplexed.wait_for_worker",
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
        timeout_sec: float | None,
        event_handler: Callable[[JSONDict], Awaitable[None]] | None = None,
    ) -> JSONDict:
        connection = await self._get_connection(worker_id)
        return await execute_outbound_ipc_request(
            encoding_pool=self._encoding_pool,
            codec=self._codec,
            connection=connection,
            worker_id=int(worker_id),
            method=method,
            request_id=request_id,
            payload=payload,
            timeout_sec=timeout_sec,
            event_handler=event_handler,
            drop_connection=lambda: self._drop_connection(int(worker_id), connection),
        )

    async def _get_connection(self, worker_id: int) -> MultiplexedConnection:
        async with self._lock:
            connection = self._connections.get(int(worker_id))
        if connection is None:
            raise ServiceUnavailableError(
                "IPC worker is not connected.",
                operation="core.ipc.multiplexed.request.no_worker",
                details={"worker_id": int(worker_id)},
            )
        return connection

    @override
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        worker_id: int | None = None
        try:
            hello = await self._codec.read_message(reader, timeout_sec=5.0)
            worker_id, worker_secret = validate_hello(hello, self._token)
            await self._authorization.require_worker_secret(worker_id, worker_secret)
            connection = MultiplexedConnection(
                worker_id=worker_id,
                reader=reader,
                writer=writer,
                write_lock=asyncio.Lock(),
            )
            await self._replace_connection(connection)
            await self._codec.write_message(
                writer,
                {"type": "hello_ack"},
                timeout_sec=5.0,
            )
            await read_multiplexed_connection(
                codec=self._codec,
                host_request_handler=self._host_request_handler,
                connection=connection,
            )
        except IPC_CONNECTION_EXCEPTIONS as exception:
            if is_ipc_peer_closed_exception(exception):
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Multiplexed IPC connection closed by peer.",
                    operation=OPERATION_IPC_CONNECTION_FAILURE,
                    details={"worker_id": worker_id},
                    level="debug",
                )
            else:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Multiplexed IPC connection failed.",
                    operation=OPERATION_IPC_CONNECTION_FAILURE,
                    details={"worker_id": worker_id},
                    level="warning",
                )
        finally:
            if worker_id is not None:
                await self._drop_if_current(worker_id, writer)
            await close_ipc_writer(writer, worker_id=worker_id)

    async def _replace_connection(self, connection: MultiplexedConnection) -> None:
        async with self._lock:
            old = self._connections.get(connection.worker_id)
            self._connections[connection.worker_id] = connection
        if old is not None:
            await close_connection(old)

    async def _drop_connection(
        self,
        worker_id: int,
        connection: MultiplexedConnection,
    ) -> None:
        async with self._lock:
            current = self._connections.get(int(worker_id))
            if current is connection:
                self._connections.pop(int(worker_id), None)
        await close_connection(connection)

    async def _drop_if_current(
        self,
        worker_id: int,
        writer: asyncio.StreamWriter,
    ) -> None:
        async with self._lock:
            current = self._connections.get(int(worker_id))
            if current is not None and current.writer is writer:
                self._connections.pop(int(worker_id), None)
                fail_pending(current, "IPC worker connection closed.")
