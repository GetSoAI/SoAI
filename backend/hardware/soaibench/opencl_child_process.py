"""SoAI - SoAIBench OpenCL child process ownership [backend/hardware/soaibench/opencl_child_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ProcessError
from core.process.termination import terminate_subprocess_gracefully
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("OpenCLChildProcessOwner",)

CHILD_OPERATION = "hardware.soaibench.opencl_child"


class OpenCLChildProcessOwner:
    def __init__(self, process: asyncio.subprocess.Process, logger: LoggerProtocol) -> None:
        self.process = process
        self._logger = logger
        self._close_lock = asyncio.Lock()
        self.closed = False
        self.degraded = False
        self._termination_requested = False

    async def close(self) -> None:
        async with self._close_lock:
            if self.closed:
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
                        "SoAIBench OpenCL child exit could not be verified.",
                        operation=CHILD_OPERATION,
                        cause=pipe_error,
                    ) from pipe_error
            except (ProcessError, asyncio.CancelledError):
                self.degraded = True
                raise
            self._record_exit(return_code)

    async def _close_stdin_and_wait(self) -> int:
        async with asyncio.timeout(float(RESPONSIVE_TIMEOUT_SEC)):
            if self.process.stdin is not None:
                self.process.stdin.close()
                await self.process.stdin.wait_closed()
            return await self.process.wait()

    async def _terminate_and_wait(self) -> int | None:
        if self.process.returncode is not None:
            return self.process.returncode
        self._termination_requested = True
        try:
            await terminate_subprocess_gracefully(
                self.process,
                logger=self._logger,
                operation=CHILD_OPERATION,
                process_group=os.name != "nt",
            )
        except (ProcessError, asyncio.CancelledError):
            self.degraded = True
            raise
        return self.process.returncode

    def _record_exit(self, return_code: int | None) -> None:
        if return_code is None:
            self.degraded = True
            raise ProcessError(
                "SoAIBench OpenCL child exit could not be verified.",
                operation=CHILD_OPERATION,
            )
        self.closed = True
        self.degraded = False
        self._logger.debug("SoAIBench OpenCL child exited with code %s.", return_code)
        if return_code != 0 and not self._termination_requested:
            raise ProcessError(
                "SoAIBench OpenCL child exited unexpectedly.",
                operation=CHILD_OPERATION,
                details={"return_code": return_code},
            )
