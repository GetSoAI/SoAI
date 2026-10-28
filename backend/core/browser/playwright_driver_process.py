"""SoAI - Playwright driver process and retained cleanup ownership [backend/core/browser/playwright_driver_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.process.termination import terminate_subprocess_gracefully
from core.system.async_command_streams import close_managed_process_pipes
from core.system.async_process_spawning import (
    ManagedAsyncProcess,
    retain_managed_process_cleanup,
    spawn_async_process,
    spawn_managed_async_process,
    wait_for_managed_process_group,
)
from core.system.subprocess_platform import windows_no_window_creationflags
from core.timing.constants import CONTROL_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC

__all__ = ("PlaywrightDriverProcess",)

LOGGER_NAME = "SoAI.core.browser.playwright_driver_process"
OPERATION_CLOSE = "core.browser.playwright_pipe_transport.close"


class PlaywrightDriverProcess:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.process: asyncio.subprocess.Process | ManagedAsyncProcess | None = None
        self.stopped: asyncio.Future[None] = loop.create_future()
        self._close_lock = asyncio.Lock()
        self._pipes_closed = False
        self._input_closed = False
        self._cleanup_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._cleanup_callback_index = 0

    @property
    def is_reaped(self) -> bool:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            return self._pipes_closed and self._cleanup_callback_index == len(
                self._cleanup_callbacks
            )
        return process is None or process.returncode is not None

    @property
    def return_code(self) -> int | None:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            return process.process.returncode
        return process.returncode if process is not None else None

    @property
    def input_writer(self) -> asyncio.StreamWriter | None:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            return process.stdin_writer
        return process.stdin if process is not None else None

    @property
    def output_reader(self) -> asyncio.StreamReader | None:
        process = self.process
        if isinstance(process, ManagedAsyncProcess):
            return process.stdout_reader
        return process.stdout if process is not None else None

    def stop_input(self) -> None:
        writer = self.input_writer
        if writer is not None and not self._input_closed:
            writer.close()
            self._input_closed = True

    async def start(self, command: Sequence[str], environment: Mapping[str, str]) -> None:
        try:
            if is_windows():
                self.process = await spawn_async_process(
                    command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None,
                    env=environment,
                    start_new_session=False,
                    creationflags=windows_no_window_creationflags(),
                    limit=32768,
                )
            else:
                self.process = await spawn_managed_async_process(
                    command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None,
                    env=environment,
                    creationflags=windows_no_window_creationflags(),
                    limit=32768,
                )
        except ProcessGroupCleanupError as exception:
            self.process = retain_managed_process_cleanup(exception)
            self._cleanup_callbacks.extend(exception.owned_cleanup_callbacks)
            raise

    async def close(self) -> None:
        async with self._close_lock:
            if self.stopped.done():
                if self.is_reaped:
                    self.stopped.result()
                    return
                self.stopped = asyncio.get_running_loop().create_future()
            self.stop_input()
            try:
                process = self.process
                if isinstance(process, ManagedAsyncProcess):
                    await self._close_managed(process)
                elif process is not None:
                    try:
                        await asyncio.wait_for(process.wait(), timeout=CONTROL_TIMEOUT_SEC)
                    except TimeoutError:
                        await terminate_subprocess_gracefully(
                            process,
                            graceful_timeout_sec=float(RESPONSIVE_TIMEOUT_SEC),
                            logger=get_logger(LOGGER_NAME),
                            operation=OPERATION_CLOSE,
                            process_group=False,
                        )
                while self._cleanup_callback_index < len(self._cleanup_callbacks):
                    await self._cleanup_callbacks[self._cleanup_callback_index]()
                    self._cleanup_callback_index += 1
            except (ProcessGroupCleanupError, asyncio.CancelledError):
                raise
            except Exception as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerce_to_soai_error(exception, operation=OPERATION_CLOSE),
                    message="Playwright driver shutdown failed.",
                    operation=OPERATION_CLOSE,
                )
                self.stopped.set_exception(exception)
                self.stopped.exception()
                raise
            self.stopped.set_result(None)

    async def _close_managed(self, process: ManagedAsyncProcess) -> None:
        if self._pipes_closed:
            return
        try:
            await wait_for_managed_process_group(
                process.process, timeout_sec=float(CONTROL_TIMEOUT_SEC)
            )
        except TimeoutError:
            await terminate_subprocess_gracefully(
                process.process,
                graceful_timeout_sec=float(RESPONSIVE_TIMEOUT_SEC),
                logger=get_logger(LOGGER_NAME),
                operation=OPERATION_CLOSE,
                process_group=True,
            )
        except ProcessGroupCleanupError:
            raise
        except (ProcessError, OSError, ValueError) as exception:
            raise ProcessGroupCleanupError(
                "Playwright owned process-group observation failed.",
                process=process.process,
                read_connections=process.connections,
                stdin_writer=process.stdin_writer,
                operation=OPERATION_CLOSE,
                cause=exception,
            ) from exception
        await close_managed_process_pipes(
            process.process, process.connections, stdin_writer=process.stdin_writer
        )
        self._pipes_closed = True
