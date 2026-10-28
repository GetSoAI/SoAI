"""SoAI - Framed Playwright driver subprocess transport [backend/core/browser/playwright_pipe_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from playwright._impl._driver import compute_driver_executable, get_driver_env
from playwright._impl._transport import Transport

from core.browser.playwright_cleanup import (
    finish_playwright_close_stage,
    preserve_playwright_primary_failure,
)
from core.browser.playwright_driver_commands import (
    resolve_playwright_driver_command,
    resolve_playwright_driver_environment,
)
from core.browser.playwright_driver_errors import PlaywrightDriverConnectionClosedError
from core.browser.playwright_driver_process import PlaywrightDriverProcess
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exceptions import ProcessError, StateError
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    YIELD_CONTROL_SEC,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("PlaywrightPipeTransport",)


class PlaywrightPipeTransport(Transport):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop)
        self._driver = PlaywrightDriverProcess(loop)
        self._stop_requested = False
        self.on_terminated: Callable[[], Awaitable[None]] | None = None
        self.on_started: Callable[[], None] | None = None

    @property
    def is_reaped(self) -> bool:
        return self._driver.is_reaped

    @property
    def close_failure(self) -> BaseException | None:
        if not self._driver.stopped.done() or self._driver.stopped.cancelled():
            return None
        return self._driver.stopped.exception()

    @property
    def is_running(self) -> bool:
        return (
            not self._stop_requested
            and not self.on_error_future.done()
            and not self._driver.stopped.done()
            and self._driver.process is not None
            and self._driver.return_code is None
        )

    @override
    def request_stop(self) -> None:
        self._stop_requested = True
        self._driver.stop_input()

    @override
    async def wait_until_stopped(self) -> None:
        await asyncio.shield(self._driver.stopped)

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
        await self._driver.start(command, resolve_playwright_driver_environment(get_driver_env()))
        if self._stop_requested:
            self.request_stop()
            raise asyncio.CancelledError

    @override
    async def run(self) -> None:
        reader = self._driver.output_reader
        if reader is None:
            raise StateError("Playwright driver output pipe is unavailable.")
        try:
            if self.on_started is not None:
                self.on_started()
            while not self._stop_requested:
                try:
                    header = await self._read_header(reader)
                    length = int.from_bytes(header, byteorder="little", signed=False)
                    fragments: list[bytes] = []
                    while length and not self._stop_requested:
                        fragment = await asyncio.wait_for(
                            reader.readexactly(min(length, 32768)),
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
            primary_exception = sys.exception()
            if isinstance(primary_exception, Exception):
                self.record_failure(primary_exception)
            finalizer = self.on_terminated
            try:
                await uncancel_then_cleanup(
                    finalizer()
                    if finalizer is not None
                    else finish_playwright_close_stage(
                        self.close(),
                        primary_exception,
                        already_reported_failure=lambda: self.close_failure,
                        cleanup_action="Playwright transport cleanup",
                    )
                )
            finally:
                preserve_playwright_primary_failure(primary_exception, sys.exception())

    async def _read_header(self, reader: asyncio.StreamReader) -> bytes:
        task = create_ephemeral_task(
            reader.readexactly(4), name="core.browser.playwright.header", log_exceptions=False
        )
        try:
            while True:
                done, _pending = await asyncio.wait(
                    {task, self.on_error_future},
                    timeout=BACKGROUND_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if self.on_error_future in done:
                    self.on_error_future.result()
                if task in done:
                    return task.result()
                if self._stop_requested:
                    raise asyncio.CancelledError
        finally:
            await uncancel_then_cleanup(cancel_and_await_task(task))

    @override
    def send(self, message: JSONDict) -> None:
        writer = self._driver.input_writer
        if self._stop_requested or writer is None:
            self.record_failure(
                PlaywrightDriverConnectionClosedError(
                    "Connection closed while reading from the driver: input pipe unavailable.",
                    operation="core.browser.playwright_pipe_transport.send",
                )
            )
            self.request_stop()
            return
        data = self.serialize_message(message)
        try:
            writer.write(len(data).to_bytes(4, byteorder="little", signed=False) + data)
        except (OSError, RuntimeError) as exception:
            self.record_failure(
                PlaywrightDriverConnectionClosedError(
                    "Connection closed while reading from the driver: input pipe write failed.",
                    operation="core.browser.playwright_pipe_transport.send",
                    cause=exception,
                )
            )
            self.request_stop()

    async def close(self) -> None:
        self.request_stop()
        await self._driver.close()
