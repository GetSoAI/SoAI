"""SoAI - App-owned finite Playwright session resources [backend/core/browser/playwright_session_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.browser.playwright_cleanup import await_playwright_caller_cleanup
from core.browser.playwright_lifecycle import (
    PlaywrightDriverSession,
    acquire_playwright_session,
    begin_playwright_session_close,
)
from core.browser.protocols import PlaywrightScopeTaskProtocol
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import ProcessError, StateError
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("PlaywrightSessionResources",)

OPERATION_CLOSE_SESSION = "core.browser.playwright_session_resources.close_session"


async def _close_owned_session(session: PlaywrightDriverSession) -> None:
    task = begin_playwright_session_close(session)
    completed, _pending = await asyncio.wait({task}, timeout=CONTROL_TIMEOUT_SEC)
    if not completed:
        raise ProcessError(
            "Playwright session cleanup remains pending after its deadline.",
            operation=OPERATION_CLOSE_SESSION,
        ) from TimeoutError("Playwright session cleanup timed out.")
    if task.cancelled():
        raise ProcessError(
            "Playwright session cleanup was cancelled.", operation=OPERATION_CLOSE_SESSION
        ) from asyncio.CancelledError()
    exception = task.exception()
    if exception is None:
        return
    if not isinstance(exception, Exception):
        raise exception
    result = session.close_result
    if (
        session.resources_closed
        and result.done()
        and not result.cancelled()
        and result.exception() is None
        and exception is session.connection_failure
    ):
        return
    raise ProcessError(
        "Playwright session cleanup failed.", operation=OPERATION_CLOSE_SESSION
    ) from exception


class PlaywrightSessionResources:
    def __init__(self) -> None:
        self._sessions: dict[PlaywrightDriverSession, PlaywrightScopeTaskProtocol | None] = {}
        self._close_task: asyncio.Task[None] | None = None

    @property
    def resources_closed(self) -> bool:
        return not self._sessions

    @asynccontextmanager
    async def managed_session(self) -> AsyncGenerator[PlaywrightDriverSession]:
        if self._close_task is not None:
            raise StateError("Playwright session resources are shutting down.")
        for session, owner in self._sessions.items():
            if (owner is None or owner.done()) and not session.resources_closed:
                raise StateError("Previous Playwright session cleanup is incomplete.")
        session = acquire_playwright_session()
        self._sessions[session] = asyncio.current_task()
        try:
            yield session
        finally:
            if session.resources_closed:
                self._sessions.pop(session, None)
            else:
                self._sessions[session] = None

    async def _close_all(self) -> None:
        failures: list[Exception] = []
        for session in tuple(self._sessions):
            try:
                await _close_owned_session(session)
            except ProcessError as exception:
                failures.append(exception)
            finally:
                if session.resources_closed:
                    self._sessions.pop(session, None)
        if failures:
            raise ProcessError(
                "Playwright session resource cleanup failed.",
                details={
                    "failed_sessions": len(failures),
                    "retained_sessions": len(self._sessions),
                },
            ) from ExceptionGroup("Playwright session cleanup failures.", failures)

    async def close_all(self) -> None:
        task = self._close_task
        if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
            task = create_ephemeral_task(
                self._close_all(),
                name="core.browser.playwright.sessions.close",
                log_exceptions=False,
            )
            self._close_task = task
            task.add_done_callback(
                lambda completed: None if completed.cancelled() else completed.exception()
            )
        await await_playwright_caller_cleanup(task)
