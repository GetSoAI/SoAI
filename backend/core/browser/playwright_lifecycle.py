"""SoAI - Playwright startup and shutdown lifecycle [backend/core/browser/playwright_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from playwright._impl._connection import Connection
from playwright._impl._object_factory import create_remote_object
from playwright.async_api import Playwright

from core.browser.playwright_pipe_transport import PlaywrightPipeTransport
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.logging.trace import get_logger
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, CONTROL_TIMEOUT_SEC

__all__ = (
    "PlaywrightDriverSession",
    "managed_playwright",
    "start_playwright_session",
    "stop_playwright_session",
)

LOGGER_NAME = "SoAI.core.browser.playwright_lifecycle"
OPERATION_START_CLEANUP = "core.browser.playwright_lifecycle.start_cleanup"
OPERATION_CONNECTION = "core.browser.playwright_lifecycle.connection"
OPERATION_STOP = "core.browser.playwright_lifecycle.stop"


@dataclass(frozen=True, slots=True)
class PlaywrightDriverSession:
    playwright: Playwright
    connection: Connection
    transport: PlaywrightPipeTransport
    connection_task: asyncio.Task[None]
    close_lock: asyncio.Lock
    close_result: asyncio.Future[None]


async def _run_connection(connection: Connection, transport: PlaywrightPipeTransport) -> None:
    try:
        await connection.run()
    except asyncio.CancelledError:
        transport.request_stop()
        raise
    except Exception as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(exception, operation=OPERATION_CONNECTION),
            message="Playwright driver connection failed.",
            operation=OPERATION_CONNECTION,
        )
        transport.record_failure(exception)
        raise
    finally:
        await uncancel_then_cleanup(transport.close())


async def _close_connection(
    connection: Connection,
    transport: PlaywrightPipeTransport,
    connection_task: asyncio.Task[None],
) -> None:
    transport.request_stop()
    try:
        await cancel_and_await_task(connection_task)
    finally:
        try:
            await transport.close()
        finally:
            try:
                await connection.stop_async()
            finally:
                for future in (transport.on_error_future, connection.playwright_future):
                    if not future.done():
                        future.cancel()
                    elif not future.cancelled():
                        future.exception()


async def _connect_playwright() -> PlaywrightDriverSession:
    loop = asyncio.get_running_loop()
    transport = PlaywrightPipeTransport(loop)
    connection = Connection(None, create_remote_object, transport, loop)
    connection_task = create_ephemeral_task(
        _run_connection(connection, transport),
        name="core.browser.playwright.connection",
        log_exceptions=False,
    )
    started = False
    try:
        await asyncio.wait(
            {transport.on_error_future, connection.playwright_future, connection_task},
            return_when=asyncio.FIRST_COMPLETED,
            timeout=BACKGROUND_TIMEOUT_SEC,
        )
        if transport.on_error_future.done():
            transport.on_error_future.result()
        if not connection.playwright_future.done():
            if not connection_task.done():
                raise TimeoutError("Playwright driver startup timed out.")
            connection_task.result()
            raise ProcessError("Playwright driver stopped before startup completed.")
        playwright = Playwright(connection.playwright_future.result())
        session = PlaywrightDriverSession(
            playwright, connection, transport, connection_task, asyncio.Lock(), loop.create_future()
        )
        started = True
        return session
    finally:
        if not started:
            await uncancel_then_cleanup(
                _finish_failed_start(connection, transport, connection_task, sys.exception())
            )


async def _finish_failed_start(
    connection: Connection,
    transport: PlaywrightPipeTransport,
    connection_task: asyncio.Task[None],
    primary_exception: BaseException | None,
) -> None:
    try:
        await _close_connection(connection, transport, connection_task)
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except Exception as exception:
        if primary_exception is exception:
            return
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


async def start_playwright_session() -> PlaywrightDriverSession:
    return await asyncio.wait_for(_connect_playwright(), timeout=BACKGROUND_TIMEOUT_SEC)


async def _close_session(session: PlaywrightDriverSession) -> None:
    async with session.close_lock:
        if session.close_result.done():
            session.close_result.result()
            return
        try:
            await _close_connection(session.connection, session.transport, session.connection_task)
        except asyncio.CancelledError:
            session.close_result.cancel()
            raise
        except Exception as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(exception, operation=OPERATION_STOP),
                message="Playwright session shutdown failed.",
                operation=OPERATION_STOP,
            )
            session.close_result.set_exception(exception)
            session.close_result.exception()
            raise
        session.close_result.set_result(None)


async def stop_playwright_session(session: PlaywrightDriverSession) -> None:
    await uncancel_then_cleanup(_close_session(session))


async def _stop_started_playwright(
    session: PlaywrightDriverSession,
    primary_exception: BaseException | None,
) -> None:
    try:
        await uncancel_then_cleanup(
            asyncio.wait_for(stop_playwright_session(session), timeout=CONTROL_TIMEOUT_SEC),
        )
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except Exception as cleanup_exception:
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
async def managed_playwright() -> AsyncGenerator[Playwright]:
    session = await start_playwright_session()
    try:
        yield session.playwright
    finally:
        await _stop_started_playwright(session, sys.exception())
