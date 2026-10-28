"""SoAI - Playwright startup and shutdown lifecycle [backend/core/browser/playwright_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from playwright._impl._driver import compute_driver_executable
from playwright._impl._object_factory import create_remote_object
from playwright.async_api import Playwright

from core.browser.playwright_cleanup import (
    await_playwright_caller_cleanup,
    preserve_playwright_primary_failure,
)
from core.browser.playwright_managed_connection import ManagedPlaywrightConnection
from core.browser.playwright_pipe_transport import PlaywrightPipeTransport
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError, StateError
from core.logging.trace import get_logger
from core.system.native_image_budget import NativeImageAllowance, native_image_allowance
from core.system.native_runtime_probes import RuntimeStartupTimeoutError, runtime_timeout_error
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, CONTROL_TIMEOUT_SEC

__all__ = (
    "PlaywrightDriverSession",
    "managed_playwright",
    "acquire_playwright_session",
    "start_playwright_session",
    "stop_playwright_session",
    "begin_playwright_session_close",
)

LOGGER_NAME = "SoAI.core.browser.playwright_lifecycle"
OPERATION_START_CLEANUP = "core.browser.playwright_lifecycle.start_cleanup"
OPERATION_STOP = "core.browser.playwright_lifecycle.stop"


@dataclass(slots=True, eq=False)
class PlaywrightDriverSession:
    connection: ManagedPlaywrightConnection
    transport: PlaywrightPipeTransport
    close_lock: asyncio.Lock
    initialized_playwright: Playwright | None = None
    connection_task: asyncio.Task[None] | None = None
    stop_task: asyncio.Task[None] | None = None

    @property
    def running_connection_task(self) -> asyncio.Task[None]:
        task = self.connection_task
        if task is None:
            raise ProcessError("Playwright driver has not been started.")
        return task

    @property
    def connection_failure(self) -> BaseException | None:
        task = self.connection_task
        if task is None or not task.done() or task.cancelled():
            return None
        return task.exception()

    @property
    def playwright(self) -> Playwright:
        playwright = self.initialized_playwright
        if playwright is None:
            raise ProcessError("Playwright driver initialization has not completed.")
        return playwright

    @property
    def close_result(self) -> asyncio.Future[None]:
        return self.connection.current_close_result

    @property
    def resources_closed(self) -> bool:
        task = self.connection_task
        return (
            (task is None or task.done())
            and (self.stop_task is None or self.stop_task.done())
            and self.connection.resources_closed
        )

    @property
    def is_active(self) -> bool:
        future = self.connection.playwright_future
        return (
            self.initialized_playwright is not None
            and future.done()
            and not future.cancelled()
            and future.exception() is None
            and self.connection_task is not None
            and not self.connection_task.done()
            and self.transport.is_running
        )


def acquire_playwright_session() -> PlaywrightDriverSession:
    loop = asyncio.get_running_loop()
    transport = PlaywrightPipeTransport(loop)
    connection = ManagedPlaywrightConnection(None, create_remote_object, transport, loop)
    connection.close_result = loop.create_future()
    transport.on_terminated = connection.finish
    transport.on_started = connection.observe_initialization
    return PlaywrightDriverSession(connection, transport, asyncio.Lock())


async def _connect_playwright(
    session: PlaywrightDriverSession, allowance: NativeImageAllowance
) -> PlaywrightDriverSession:
    connection = session.connection
    transport = session.transport
    connection_task = session.running_connection_task
    await asyncio.wait(
        {transport.on_error_future, connection.playwright_future, connection_task},
        return_when=asyncio.FIRST_COMPLETED,
        timeout=allowance.seconds,
    )
    if transport.on_error_future.done():
        transport.on_error_future.result()
    if not connection.playwright_future.done():
        if not connection_task.done():
            raise runtime_timeout_error(
                RuntimeStartupTimeoutError,
                subject="The managed browser driver startup",
                allowance=allowance,
            )
        connection_task.result()
        raise ProcessError("Playwright driver stopped before startup completed.")
    session.initialized_playwright = Playwright(connection.playwright_future.result())
    return session


async def _finish_failed_start(
    connection: ManagedPlaywrightConnection,
    transport: PlaywrightPipeTransport,
    connection_task: asyncio.Task[None],
    primary_exception: BaseException | None,
) -> None:
    try:
        transport.request_stop()
        try:
            await cancel_and_await_task(connection_task)
        finally:
            await connection.finish()
    except asyncio.CancelledError as exception:
        if primary_exception is not None and (
            isinstance(primary_exception, asyncio.CancelledError)
            or not current_task_has_pending_cancellation()
        ):
            primary_exception.add_note("Playwright cleanup was cancelled before completion.")
            return
        raise_cancelled_error(exception)
    except Exception as exception:
        if primary_exception is exception:
            return
        close_result = connection.current_close_result
        if not (
            close_result.done()
            and not close_result.cancelled()
            and close_result.exception() is exception
        ):
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(exception, operation=OPERATION_START_CLEANUP),
                message="Playwright startup cleanup failed.",
                operation=OPERATION_START_CLEANUP,
            )
        if primary_exception is not None:
            primary_exception.add_note(f"Playwright startup cleanup failed: {exception}")
            return
        raise


async def start_playwright_session(session: PlaywrightDriverSession) -> PlaywrightDriverSession:
    if (
        session.connection_task is not None
        or session.connection.close_task is not None
        or session.stop_task is not None
    ):
        raise StateError("Playwright driver session has already been started or closed.")
    connection = session.connection
    driver_executable, _driver_entrypoint = compute_driver_executable()
    allowance = await asyncio.to_thread(
        native_image_allowance,
        BACKGROUND_TIMEOUT_SEC,
        roots=(os.path.dirname(driver_executable),),
    )
    session.connection_task = create_ephemeral_task(
        connection.run(),
        name="core.browser.playwright.connection",
        log_exceptions=False,
    )
    session.connection_task.add_done_callback(
        lambda completed: None if completed.cancelled() else completed.exception()
    )
    started = False
    try:
        result = await _connect_playwright(session, allowance)
        started = True
        return result
    finally:
        if not started:
            await uncancel_then_cleanup(
                _finish_failed_start(
                    connection, session.transport, session.running_connection_task, sys.exception()
                )
            )


async def _close_session(session: PlaywrightDriverSession) -> None:
    async with session.close_lock:
        if session.connection_task is None:
            await session.connection.finish()
            return
        previous = session.connection.close_task
        session.transport.request_stop()
        if (
            previous is not None
            and previous.done()
            and not (session.running_connection_task.done() and session.connection.resources_closed)
        ):
            retained_group_failure: ProcessGroupCleanupError | None = None
            try:
                try:
                    await cancel_and_await_task(session.running_connection_task)
                except ProcessGroupCleanupError as exception:
                    retained_group_failure = exception
            finally:
                primary_exception = sys.exception()
                try:
                    await session.connection.finish(retry=True)
                finally:
                    preserve_playwright_primary_failure(primary_exception, sys.exception())
            if retained_group_failure is not None and not session.connection.resources_closed:
                raise retained_group_failure
        else:
            await cancel_and_await_task(session.running_connection_task)
        await asyncio.shield(session.close_result)


def begin_playwright_session_close(session: PlaywrightDriverSession) -> asyncio.Task[None]:
    task = session.stop_task
    if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
        task = create_ephemeral_task(
            _close_session(session),
            name="core.browser.playwright.session.close",
            log_exceptions=False,
        )
        session.stop_task = task
        task.add_done_callback(
            lambda completed: None if completed.cancelled() else completed.exception()
        )
    return task


async def stop_playwright_session(session: PlaywrightDriverSession) -> None:
    await await_playwright_caller_cleanup(begin_playwright_session_close(session))


async def _stop_started_playwright(
    session: PlaywrightDriverSession,
    primary_exception: BaseException | None,
) -> None:
    try:
        await uncancel_then_cleanup(
            asyncio.wait_for(stop_playwright_session(session), timeout=CONTROL_TIMEOUT_SEC),
        )
    except asyncio.CancelledError as exception:
        if primary_exception is not None and (
            isinstance(primary_exception, asyncio.CancelledError)
            or not current_task_has_pending_cancellation()
        ):
            primary_exception.add_note("Playwright cleanup was cancelled before completion.")
            return
        raise_cancelled_error(exception)
    except Exception as cleanup_exception:
        close_result = session.close_result
        if not (
            close_result.done()
            and not close_result.cancelled()
            and close_result.exception() is cleanup_exception
        ):
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(cleanup_exception, operation=OPERATION_STOP),
                message="Playwright shutdown failed.",
                operation=OPERATION_STOP,
            )
        if primary_exception is not None:
            primary_exception.add_note(f"Playwright shutdown failed: {cleanup_exception}")
            return
        raise


@asynccontextmanager
async def managed_playwright(session: PlaywrightDriverSession) -> AsyncGenerator[Playwright]:
    await start_playwright_session(session)
    try:
        yield session.playwright
    finally:
        await _stop_started_playwright(session, sys.exception())
