"""SoAI - SoAIBench OpenCL child process ownership [backend/hardware/soaibench/opencl_child_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.concurrency.singleflight import AsyncSingleflight, ResultCopyMode
from core.errors.exceptions import ProcessError
from core.process.termination import (
    poll_process_exit_without_reaping,
    terminate_subprocess_gracefully,
)
from core.system.async_command_streams import close_managed_process_pipes
from core.system.async_process_spawning import ManagedAsyncProcess, wait_for_managed_process_group
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.logging.protocols import LoggerProtocol

__all__ = ("CHILD_CLEANUP_TIMEOUT_SEC", "OpenCLChildProcessOwner")

CHILD_OPERATION = "hardware.soaibench.opencl_child"
CHILD_CLEANUP_TIMEOUT_SEC = 3 * RESPONSIVE_TIMEOUT_SEC + LOCAL_IO_TIMEOUT_SEC


class OpenCLChildProcessOwner:
    def __init__(
        self,
        process: asyncio.subprocess.Process | ManagedAsyncProcess,
        logger: LoggerProtocol,
        *,
        cleanup_pool: BoundedBlockingPool | None = None,
    ) -> None:
        self.process = process
        self._logger = logger
        self._cleanup_pool = cleanup_pool
        self._cleanup_flight = AsyncSingleflight[str, None](ResultCopyMode.NONE)
        self.closed = False
        self.degraded = isinstance(process, ManagedAsyncProcess) and (process.stdout_reader is None)
        self._termination_requested = False

    async def close(self) -> None:
        if self.closed:
            return
        try:
            await self._cleanup_flight.execute_or_wait(CHILD_OPERATION, self._close_once)
        except asyncio.CancelledError:
            if not self.closed:
                self.degraded = True
            raise

    async def _close_once(self) -> None:
        if self.closed:
            return
        if isinstance(self.process, ManagedAsyncProcess):
            await self._close_managed_group(self.process)
            return
        if self.process.returncode is not None:
            self._record_exit(self.process.returncode)
            return
        return_code: int | None
        try:
            return_code = await self._close_stdin_and_wait()
        except TimeoutError:
            return_code = await self._terminate_and_wait()
        except (OSError, ValueError) as pipe_error:
            if self.process.returncode is None:
                return_code = await self._terminate_and_wait()
            else:
                return_code = self.process.returncode
            if return_code is None:
                self.degraded = True
                raise ProcessError(
                    "SoAI Bench OpenCL child exit could not be verified.",
                    operation=CHILD_OPERATION,
                    cause=pipe_error,
                ) from pipe_error
        except (ProcessError, asyncio.CancelledError):
            self.degraded = True
            raise
        self._record_exit(return_code)

    async def _close_managed_group(self, resource: ManagedAsyncProcess) -> None:
        started = time.monotonic()
        deadline = deadline_after(CHILD_CLEANUP_TIMEOUT_SEC)
        cleanup_phase = "close_stdin"
        try:
            if resource.process.returncode is None:
                graceful_timeout = min(float(RESPONSIVE_TIMEOUT_SEC), deadline.remaining_seconds())
                try:
                    async with asyncio.timeout(graceful_timeout):
                        if resource.stdin_writer is not None:
                            resource.stdin_writer.close()
                            await resource.stdin_writer.wait_closed()
                        cleanup_phase = "observe_owned_session"
                        await wait_for_managed_process_group(
                            resource.process, timeout_sec=graceful_timeout, pool=self._cleanup_pool
                        )
                except (OSError, ValueError):
                    if resource.process.returncode is None:
                        self._termination_requested = True
                        cleanup_phase = "terminate_owned_session"
                        await terminate_subprocess_gracefully(
                            resource.process,
                            logger=self._logger,
                            operation=CHILD_OPERATION,
                            process_group=True,
                            deadline=deadline,
                            pool=self._cleanup_pool,
                        )
            cleanup_phase = "close_owned_pipes"
            await close_managed_process_pipes(
                resource.process,
                resource.connections,
                stdin_writer=resource.stdin_writer,
            )
        except (ProcessError, OSError, ValueError, asyncio.CancelledError) as exception:
            self.degraded = True
            if isinstance(exception, ProcessError):
                observed_exit = None
                session_id = None
                observation_failure = None
                try:
                    observed_exit = poll_process_exit_without_reaping(resource.process)
                    session_id = os.getsid(resource.process.pid)
                except OSError as observation_exception:
                    observation_failure = type(observation_exception).__name__
                details = exception.details if exception.details is not None else {}
                details.update(
                    {
                        "child_pid": resource.process.pid,
                        "group_id": resource.process.pid,
                        "session_id": session_id,
                        "observed_child_exit": observed_exit,
                        "cleanup_phase": cleanup_phase,
                        "elapsed_seconds": time.monotonic() - started,
                        "exit_observation_timeout_seconds": RESPONSIVE_TIMEOUT_SEC,
                        "cleanup_timeout_seconds": CHILD_CLEANUP_TIMEOUT_SEC,
                        "pipe_close_timeout_seconds": LOCAL_IO_TIMEOUT_SEC,
                        "observation_failure": observation_failure,
                        "cleanup_failure": type(exception).__name__,
                    }
                )
                exception.details = details
            raise
        self._record_exit(resource.process.returncode)

    async def _close_stdin_and_wait(self) -> int:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            raise ProcessError(
                "OpenCL managed cleanup requires full group ownership.", operation=CHILD_OPERATION
            )
        async with asyncio.timeout(float(RESPONSIVE_TIMEOUT_SEC)):
            if process.stdin is not None:
                process.stdin.close()
                await process.stdin.wait_closed()
            return await process.wait()

    async def _terminate_and_wait(self) -> int | None:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            raise ProcessError(
                "OpenCL managed cleanup requires full group ownership.", operation=CHILD_OPERATION
            )
        if process.returncode is not None:
            return process.returncode
        self._termination_requested = True
        try:
            await terminate_subprocess_gracefully(
                process,
                logger=self._logger,
                operation=CHILD_OPERATION,
                process_group=False,
            )
        except (ProcessError, asyncio.CancelledError):
            self.degraded = True
            raise
        return process.returncode

    def _record_exit(self, return_code: int | None) -> None:
        if return_code is None:
            self.degraded = True
            raise ProcessError(
                "SoAI Bench OpenCL child exit could not be verified.",
                operation=CHILD_OPERATION,
            )
        self.closed = True
        self.degraded = False
        self._logger.debug("SoAI Bench OpenCL child exited with code %s.", return_code)
        if return_code != 0 and not self._termination_requested:
            raise ProcessError(
                "SoAI Bench OpenCL child exited unexpectedly.",
                operation=CHILD_OPERATION,
                details={"return_code": return_code},
            )
