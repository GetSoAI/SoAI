"""SoAI - Managed IPC worker subprocess supervisor [backend/core/ipc/managed_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.managed_worker_spawn import spawn_managed_ipc_process
from core.ipc.managed_worker_startup import wait_for_worker_or_exit
from core.logging.trace import get_logger
from core.platform.os import is_posix
from core.process.termination import terminate_subprocess_gracefully

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from core.ipc.protocols import IpcConnectionWaitServerProtocol

__all__ = (
    "ManagedIpcWorker",
    "ManagedIpcWorkerDependencies",
)

OPERATION_CORE_IPC_MANAGED_WORKER_TERMINATE = "core.ipc.managed_worker.terminate"


LOGGER_NAME = "SoAI.core.ipc.managed_worker"
OPERATION = "core.ipc.managed_worker.spawn.wait_for_connect"
WORKER_TERMINATION_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    ProcessError,
    RuntimeError,
)


@dataclass(frozen=True, slots=True)
class ManagedIpcWorkerDependencies:
    worker_id: int
    argv: Sequence[str]
    cwd: str
    env: Mapping[str, str]
    diagnostic_log_path: str = ""

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ManagedIpcWorkerDependencies",
            argv=self.argv,
            cwd=self.cwd,
            diagnostic_log_path=self.diagnostic_log_path,
            env=self.env,
            worker_id=self.worker_id,
        )


class ManagedIpcWorker:
    def __init__(self, deps: ManagedIpcWorkerDependencies) -> None:
        self.worker_id = int(deps.worker_id)
        self.argv = deps.argv
        self.cwd = deps.cwd
        self.env = deps.env
        self.diagnostic_log_path = deps.diagnostic_log_path
        self.process: asyncio.subprocess.Process | None = None
        self.spawn_lock = asyncio.Lock()

    async def spawn(
        self,
        *,
        server: IpcConnectionWaitServerProtocol,
        startup_timeout_sec: float,
    ) -> None:
        async with self.spawn_lock:
            existing = self.process
            if existing is not None and existing.returncode is None:
                await wait_for_worker_or_exit(
                    server,
                    worker_id=int(self.worker_id),
                    process=existing,
                    diagnostic_log_path=str(self.diagnostic_log_path),
                    startup_timeout_sec=float(startup_timeout_sec),
                )
                return
            argv_list = [str(part) for part in self.argv]
            if not argv_list:
                raise ValidationError("argv is required to spawn managed worker.")
            cwd_value = os.path.abspath(str(self.cwd or "").strip())
            if not cwd_value:
                raise ValidationError("cwd is required to spawn managed worker.")
            try:
                self.process = await spawn_managed_ipc_process(
                    argv_list,
                    cwd=cwd_value,
                    env=self.env,
                    diagnostic_log_path=str(self.diagnostic_log_path),
                    start_new_session=is_posix(),
                )
            except OSError as exception:
                raise ProcessError(
                    "Failed to spawn IPC worker process.",
                    operation="core.ipc.managed_worker.spawn.start",
                    details={
                        "diagnostic_log_path": str(self.diagnostic_log_path),
                        "worker_id": int(self.worker_id),
                    },
                    cause=exception,
                ) from exception
            try:
                await wait_for_worker_or_exit(
                    server,
                    worker_id=int(self.worker_id),
                    process=self.process,
                    diagnostic_log_path=str(self.diagnostic_log_path),
                    startup_timeout_sec=float(startup_timeout_sec),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                logger = get_logger(LOGGER_NAME)
                error = coerce_to_soai_error(
                    exception,
                    operation="core.ipc.managed_worker.spawn.wait_for_connect",
                    details={"worker_id": int(self.worker_id)},
                )
                log_exception(
                    logger,
                    error,
                    message="Managed IPC worker failed to connect; terminating worker subprocess.",
                    operation=OPERATION,
                    details={"worker_id": int(self.worker_id)},
                    level="warning",
                )
                await self._terminate_after_spawn_failure(
                    operation="core.ipc.managed_worker.spawn.cleanup",
                )
                if error is exception:
                    raise
                raise error from exception
            except asyncio.CancelledError:
                await self._terminate_after_spawn_failure(
                    operation="core.ipc.managed_worker.spawn.cleanup",
                )
                raise
            except ProcessError as exception:
                logger = get_logger(LOGGER_NAME)
                log_exception(
                    logger,
                    exception,
                    message="Managed IPC worker failed before connecting; terminating worker subprocess.",
                    operation=OPERATION,
                    details={"worker_id": int(self.worker_id)},
                    level="warning",
                )
                await self._terminate_after_spawn_failure(
                    operation="core.ipc.managed_worker.spawn.cleanup",
                )
                raise
            except (OSError, RuntimeError) as exception:
                logger = get_logger(LOGGER_NAME)
                error = ProcessError(
                    "Managed IPC worker failed before connecting.",
                    operation="core.ipc.managed_worker.spawn.wait_for_connect",
                    details={"worker_id": int(self.worker_id)},
                    cause=exception,
                )
                log_exception(
                    logger,
                    error,
                    message="Managed IPC worker failed before connecting; terminating worker subprocess.",
                    operation=OPERATION,
                    details={"worker_id": int(self.worker_id)},
                    level="warning",
                )
                await self._terminate_after_spawn_failure(
                    operation="core.ipc.managed_worker.spawn.cleanup",
                )
                raise error from exception

    async def terminate(self, *, operation: str) -> None:
        logger = get_logger(LOGGER_NAME)
        proc = self.process
        if proc is None:
            return
        try:
            if proc.returncode is None:
                await terminate_subprocess_gracefully(proc, logger=logger, operation=operation)
            self.process = None
        except WORKER_TERMINATION_FAILURE_EXCEPTIONS as exception:
            if proc.returncode is not None:
                self.process = None
            error = coerce_to_soai_error(
                exception,
                operation=operation,
                details={"worker_id": int(self.worker_id)},
            )
            log_exception(
                logger,
                error,
                message="Failed to terminate IPC worker process.",
                operation=OPERATION_CORE_IPC_MANAGED_WORKER_TERMINATE,
                details={"worker_id": int(self.worker_id)},
                level="warning",
            )
            raise ProcessError(
                "Failed to terminate IPC worker process.",
                operation=operation,
                details={"worker_id": int(self.worker_id)},
                cause=exception,
            ) from exception

    async def _terminate_after_spawn_failure(self, *, operation: str) -> None:
        try:
            await self.terminate(operation=operation)
        except WORKER_TERMINATION_FAILURE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to terminate IPC worker after spawn failure.",
                operation=operation,
                details={"worker_id": int(self.worker_id)},
                level="warning",
            )
