"""SoAI - Framed Playwright driver subprocess transport [backend/core/browser/playwright_pipe_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from playwright._impl._driver import compute_driver_executable, get_driver_env
from playwright._impl._transport import Transport

from core.browser.playwright_driver_commands import (
    resolve_playwright_driver_command,
    resolve_playwright_driver_environment,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, StateError
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.process.termination import terminate_subprocess_gracefully
from core.system.async_process_spawning import spawn_async_process
from core.system.subprocess_platform import windows_no_window_creationflags
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    CONTROL_TIMEOUT_SEC,
    RESPONSIVE_TIMEOUT_SEC,
    YIELD_CONTROL_SEC,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("PlaywrightPipeTransport",)

LOGGER_NAME = "SoAI.core.browser.playwright_pipe_transport"
OPERATION_CLOSE = "core.browser.playwright_pipe_transport.close"


class PlaywrightPipeTransport(Transport):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop)
        self._process: asyncio.subprocess.Process | None = None
        self._stop_requested = False
        self._stopped: asyncio.Future[None] = loop.create_future()
        self._close_lock = asyncio.Lock()

    @override
    def request_stop(self) -> None:
        self._stop_requested = True
        process = self._process
        if process is not None and process.stdin is not None:
            process.stdin.close()

    @override
    async def wait_until_stopped(self) -> None:
        await asyncio.shield(self._stopped)

    def record_failure(self, exception: Exception) -> None:
        if not self.on_error_future.done():
            self.on_error_future.set_exception(exception)
            return
        if self.on_error_future.cancelled():
            raise StateError(
                "Playwright driver failure notification was cancelled before shutdown."
            )
        primary = self.on_error_future.exception()
        if primary is None:
            raise StateError("Playwright driver failure notification has an invalid success state.")
        if primary is not exception:
            primary.add_note(f"Additional Playwright driver failure: {exception}")

    @override
    async def connect(self) -> None:
        if self._stop_requested:
            raise asyncio.CancelledError
        executable, entrypoint = compute_driver_executable()
        command = resolve_playwright_driver_command(executable, entrypoint, ("run-driver",))
        self._process = await spawn_async_process(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,
            env=resolve_playwright_driver_environment(get_driver_env()),
            start_new_session=not is_windows(),
            creationflags=windows_no_window_creationflags(),
            limit=32768,
        )
        if self._stop_requested:
            self.request_stop()
            raise asyncio.CancelledError

    @override
    async def run(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            raise StateError("Playwright driver output pipe is unavailable.")
        try:
            while not self._stop_requested:
                try:
                    header = await self._read_header(process.stdout)
                    length = int.from_bytes(header, byteorder="little", signed=False)
                    fragments: list[bytes] = []
                    while length and not self._stop_requested:
                        fragment = await asyncio.wait_for(
                            process.stdout.readexactly(min(length, 32768)),
                            timeout=BACKGROUND_TIMEOUT_SEC,
                        )
                        fragments.append(fragment)
                        length -= len(fragment)
                    if not self._stop_requested:
                        self.on_message(self.deserialize_message(b"".join(fragments)))
                        await asyncio.sleep(YIELD_CONTROL_SEC)
                except asyncio.IncompleteReadError:
                    if not self._stop_requested:
                        self.record_failure(
                            ProcessError(
                                "Connection closed while reading from the driver",
                                operation="core.browser.playwright_pipe_transport.read",
                            )
                        )
                    break
        finally:
            await uncancel_then_cleanup(self.close())

    async def _read_header(self, reader: asyncio.StreamReader) -> bytes:
        task = create_ephemeral_task(
            reader.readexactly(4), name="core.browser.playwright.header", log_exceptions=False
        )
        try:
            while True:
                try:
                    return await asyncio.wait_for(
                        asyncio.shield(task), timeout=BACKGROUND_TIMEOUT_SEC
                    )
                except TimeoutError as exception:
                    if self._stop_requested:
                        raise asyncio.CancelledError from exception
        finally:
            await uncancel_then_cleanup(cancel_and_await_task(task))

    @override
    def send(self, message: JSONDict) -> None:
        process = self._process
        if self._stop_requested or process is None or process.stdin is None:
            raise ProcessError(
                "Playwright driver input pipe is unavailable.",
                operation="core.browser.playwright_pipe_transport.send",
            )
        data = self.serialize_message(message)
        process.stdin.write(len(data).to_bytes(4, byteorder="little", signed=False) + data)

    async def close(self) -> None:
        async with self._close_lock:
            if self._stopped.done():
                self._stopped.result()
                return
            self.request_stop()
            try:
                process = self._process
                if process is not None:
                    try:
                        await asyncio.wait_for(process.wait(), timeout=CONTROL_TIMEOUT_SEC)
                    except TimeoutError:
                        await terminate_subprocess_gracefully(
                            process,
                            graceful_timeout_sec=float(RESPONSIVE_TIMEOUT_SEC),
                            logger=get_logger(LOGGER_NAME),
                            operation="core.browser.playwright_pipe_transport.close",
                            process_group=not is_windows(),
                        )
            except asyncio.CancelledError:
                self._stopped.cancel()
                raise
            except Exception as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerce_to_soai_error(exception, operation=OPERATION_CLOSE),
                    message="Playwright driver shutdown failed.",
                    operation=OPERATION_CLOSE,
                )
                self._stopped.set_exception(exception)
                self._stopped.exception()
                raise
            self._stopped.set_result(None)
