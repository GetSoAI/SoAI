"""SoAI - Managed media IPC gateway cleanup [backend/core/media/ipc_gateway_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Never

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ServiceUnavailableError, SoAITimeoutError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.ipc.ndjson import NdjsonCodec
from core.ipc.protocols import ManagedIpcWorkerProtocol
from core.ipc.server import LocalIpcServer
from core.ipc.settings import resolve_ipc_max_message_bytes
from core.media.protocols import MediaIpcServerLifecycleProtocol
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

__all__ = (
    "MediaIpcGatewayState",
    "MediaIpcGatewayStateDependencies",
    "build_media_ipc_gateway",
    "cleanup_failed_media_gateway_request",
    "cleanup_failed_media_gateway_start",
    "raise_after_media_gateway_request_failure",
    "shutdown_media_gateway",
)


@dataclass(frozen=True, slots=True)
class MediaIpcGatewayStateDependencies:
    server: MediaIpcServerLifecycleProtocol
    operation: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MediaIpcGatewayStateDependencies",
            server=self.server,
            operation=self.operation,
        )


class MediaIpcGatewayState:
    def __init__(self, deps: MediaIpcGatewayStateDependencies) -> None:
        self._server = deps.server
        self._operation = deps.operation
        self._worker: ManagedIpcWorkerProtocol | None = None
        self._started = False
        self._lock = asyncio.Lock()

    async def ensure_started(
        self,
        worker_builder: Callable[[], ManagedIpcWorkerProtocol],
    ) -> None:
        async with self._lock:
            if self._started:
                return
            worker = await _start_media_gateway(
                self._server,
                worker_builder,
                operation=self._operation,
            )
            self._worker = worker
            self._started = True

    async def reset(self) -> None:
        async with self._lock:
            worker = self._worker
            self._worker = None
            self._started = False
            await shutdown_media_gateway(
                self._server,
                worker,
                operation=f"{self._operation}.shutdown",
            )


def build_media_ipc_gateway(
    config: ConfigProtocol,
    operation: str,
) -> tuple[LocalIpcServer, MediaIpcGatewayState]:
    server = LocalIpcServer(
        codec=NdjsonCodec(max_line_bytes=resolve_ipc_max_message_bytes(config)),
    )
    state = MediaIpcGatewayState(
        MediaIpcGatewayStateDependencies(server=server, operation=operation),
    )
    return server, state


async def cleanup_failed_media_gateway_request(
    cleanup: Awaitable[None],
    primary_exception: BaseException,
) -> None:
    try:
        await uncancel_then_cleanup(cleanup)
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"Media IPC gateway reset failed: {cleanup_exception}")


async def raise_after_media_gateway_request_failure(
    cleanup: Awaitable[None],
    exception: ServiceUnavailableError,
    *,
    timeout_message: str,
) -> Never:
    failure: ServiceUnavailableError | SoAITimeoutError = exception
    if isinstance(exception.cause, TimeoutError):
        failure = SoAITimeoutError(timeout_message, cause=exception)
    await cleanup_failed_media_gateway_request(cleanup, failure)
    if failure is exception:
        raise exception
    raise failure from exception


async def cleanup_failed_media_gateway_start(
    server: MediaIpcServerLifecycleProtocol,
    worker: ManagedIpcWorkerProtocol | None,
    primary_exception: BaseException,
    *,
    operation: str,
) -> None:
    try:
        await uncancel_then_cleanup(
            shutdown_media_gateway(server, worker, operation=operation),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"Media IPC server cleanup failed: {cleanup_exception}")


async def _start_media_gateway(
    server: MediaIpcServerLifecycleProtocol,
    worker_builder: Callable[[], ManagedIpcWorkerProtocol],
    *,
    operation: str,
) -> ManagedIpcWorkerProtocol:
    worker: ManagedIpcWorkerProtocol | None = None
    try:
        await server.start()
        worker = worker_builder()
        await worker.spawn(server=server, startup_timeout_sec=INTERACTIVE_TIMEOUT_SEC)
    except asyncio.CancelledError as exception:
        await cleanup_failed_media_gateway_start(
            server,
            worker,
            exception,
            operation=f"{operation}.startup_failure",
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await cleanup_failed_media_gateway_start(
            server,
            worker,
            exception,
            operation=f"{operation}.startup_failure",
        )
        raise
    return worker


async def shutdown_media_gateway(
    server: MediaIpcServerLifecycleProtocol,
    worker: ManagedIpcWorkerProtocol | None,
    *,
    operation: str,
) -> None:
    failures: list[Exception] = []
    try:
        await server.shutdown()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
    if worker is not None:
        try:
            await worker.terminate(operation=operation)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures.append(exception)
    if failures:
        raise ExceptionGroup("Media IPC gateway shutdown failed.", failures)
