"""SoAI - Managed Playwright connection cleanup ownership [backend/core/browser/playwright_managed_connection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from typing import override

from playwright._impl._connection import Connection

from core.browser.playwright_cleanup import (
    finish_playwright_close_stage,
    preserve_playwright_primary_failure,
)
from core.browser.playwright_driver_errors import (
    classify_playwright_driver_connection_closed_exception,
)
from core.browser.playwright_pipe_transport import PlaywrightPipeTransport
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.logging.trace import get_logger

__all__ = ("ManagedPlaywrightConnection",)

LOGGER_NAME = "SoAI.core.browser.playwright_managed_connection"
OPERATION_CONNECTION = "core.browser.playwright_lifecycle.connection"


class ManagedPlaywrightConnection(Connection):
    _init_task: asyncio.Task[None] | None

    close_result: asyncio.Future[None] | None = None
    close_task: asyncio.Task[None] | None = None

    @property
    def current_close_result(self) -> asyncio.Future[None]:
        result = self.close_result
        if result is None:
            raise ProcessError("Playwright connection cleanup result is not initialized.")
        return result

    @property
    def resources_closed(self) -> bool:
        return (
            self.driver_transport.is_reaped
            and (self.close_task is None or self.close_task.done())
            and (self._init_task is None or self._init_task.done())
        )

    @property
    def driver_transport(self) -> PlaywrightPipeTransport:
        transport = self._transport
        if not isinstance(transport, PlaywrightPipeTransport):
            raise ProcessError("Playwright connection does not own its driver transport.")
        return transport

    def observe_initialization(self) -> None:
        if self._init_task is not None:
            self._init_task.add_done_callback(self._initialization_finished)

    def _initialization_finished(self, task: asyncio.Task[None]) -> None:
        if self._closed_error is not None:
            return
        if task.cancelled():
            failure: BaseException | None = ProcessError(
                "Playwright driver initialization was cancelled."
            )
        else:
            failure = task.exception()
        if isinstance(failure, Exception):
            self.driver_transport.record_failure(failure)
            self.driver_transport.request_stop()

    @override
    async def run(self) -> None:
        try:
            await super().run()
        except asyncio.CancelledError:
            self.driver_transport.request_stop()
            raise
        except Exception as exception:
            self.driver_transport.record_failure(exception)
            if (
                classify_playwright_driver_connection_closed_exception(
                    exception, operation=OPERATION_CONNECTION, details={}
                )
                is not None
            ):
                return
            if (
                self.close_result is not None
                and self.close_result.done()
                and not self.close_result.cancelled()
                and self.close_result.exception() is exception
            ):
                raise
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(exception, operation=OPERATION_CONNECTION),
                message="Playwright driver connection failed.",
                operation=OPERATION_CONNECTION,
            )
            raise
        finally:
            primary_exception = sys.exception()
            try:
                try:
                    await uncancel_then_cleanup(self.finish())
                finally:
                    preserve_playwright_primary_failure(primary_exception, sys.exception())
            finally:
                if not self.driver_transport.on_error_future.done():
                    self.driver_transport.on_error_future.cancel()
                elif not self.driver_transport.on_error_future.cancelled():
                    self.driver_transport.on_error_future.exception()

    async def finish(self, *, retry: bool = False) -> None:
        previous = self.close_task
        if retry and previous is not None and previous.done() and not self.resources_closed:
            if previous.cancelled() or previous.exception() is not None:
                self.close_result = asyncio.get_running_loop().create_future()
                self.close_task = None
        if self.close_task is None:
            self.close_task = create_ephemeral_task(
                self._close() if self._closed_error is None else self._retry_close(),
                name="core.browser.playwright.cleanup",
                log_exceptions=False,
            )
            self.close_task.add_done_callback(
                lambda completed: None if completed.cancelled() else completed.exception()
            )
        await asyncio.shield(self.close_task)

    async def _close(self) -> None:
        close_result = self.current_close_result
        try:
            failure = None
            if (
                self.driver_transport.on_error_future.done()
                and not self.driver_transport.on_error_future.cancelled()
            ):
                failure = self.driver_transport.on_error_future.exception()
            try:
                await finish_playwright_close_stage(
                    self._close_callbacks(failure),
                    None,
                    already_reported_failure=lambda: self.driver_transport.close_failure,
                    cleanup_action="Playwright connection cleanup",
                )
            finally:
                primary_exception = sys.exception()
                try:
                    await finish_playwright_close_stage(
                        self._finish_initialization(),
                        primary_exception,
                        already_reported_failure=lambda: self.driver_transport.close_failure,
                        cleanup_action="Playwright initialization cleanup",
                    )
                finally:
                    await finish_playwright_close_stage(
                        self.driver_transport.close(),
                        sys.exception(),
                        already_reported_failure=lambda: self.driver_transport.close_failure,
                        cleanup_action="Playwright transport cleanup",
                    )
        finally:
            primary_exception = sys.exception()
            if primary_exception is None:
                close_result.set_result(None)
            else:
                close_result.set_exception(primary_exception)
                close_result.exception()

    async def _finish_initialization(self) -> None:
        result_was_pending = not self.playwright_future.done()
        try:
            await cancel_and_await_task(self._init_task)
            if (
                result_was_pending
                and self.playwright_future.done()
                and not self.playwright_future.cancelled()
            ):
                failure = self.playwright_future.exception()
                if failure is not None:
                    raise failure
        finally:
            if not self.playwright_future.done():
                self.playwright_future.cancel()
            elif not self.playwright_future.cancelled():
                self.playwright_future.exception()

    async def _retry_close(self) -> None:
        close_result = self.current_close_result
        try:
            await finish_playwright_close_stage(
                self.driver_transport.close(),
                None,
                already_reported_failure=lambda: self.driver_transport.close_failure,
                cleanup_action="Playwright transport cleanup",
            )
        finally:
            failure = sys.exception()
            if failure is None:
                close_result.set_result(None)
            else:
                close_result.set_exception(failure)
                close_result.exception()

    async def _close_callbacks(self, failure: BaseException | None) -> None:
        callbacks = tuple(self._callbacks.values())
        try:
            self.cleanup(str(failure) if failure is not None else "")
        finally:
            for callback in callbacks:
                if callback.future.done() and not callback.future.cancelled():
                    callback.future.exception()
