"""SoAI - PTY session lifecycle coordinator [backend/terminal/pty_session_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.terminal.command_truncation import truncate_shell_command
from core.terminal.pty_validation import normalize_required_session_id
from core.terminal.requests import CreatePTYSessionRequest
from terminal.dependencies import (
    PTYIOHandlerDependencies,
    PTYSessionManagerDependencies,
    PTYSpawnerDependencies,
)
from terminal.pty_io import PTYIOHandler
from terminal.pty_loops import run_pty_busy_poll_loop, run_pty_read_loop
from terminal.pty_spawner import PTYSpawner
from terminal.session_registry import PTYSessionStore
from terminal.session_support import log_terminal_trace, require_live_session

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from terminal.types import PTYSession

__all__ = ("PTYSessionManager",)

OPERATION_TERMINAL_PTY_SESSION_MANAGER_CREATE_SESSION = (
    "terminal.pty_session_manager.create_session"
)
OPERATION_TERMINAL_PTY_SESSION_MANAGER_SHUTDOWN = "terminal.pty_session_manager.shutdown"
PTY_SESSION_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


class PTYSessionManager:

    def __init__(self, deps: PTYSessionManagerDependencies) -> None:
        self._logger = deps.logger
        self._base_dir = deps.base_dir
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._registry = PTYSessionStore()
        self._spawner = PTYSpawner(
            PTYSpawnerDependencies(base_dir=deps.base_dir, logger=deps.logger),
        )
        self._io_handler = PTYIOHandler(PTYIOHandlerDependencies(logger=deps.logger))

    async def create_session(
        self,
        request: CreatePTYSessionRequest,
    ) -> JSONDict:
        session_id = normalize_required_session_id(
            request.session_id,
            error_message="Invalid session_id.",
        )

        def _spawn_session() -> PTYSession:
            session = self._spawner.spawn(
                session_id=session_id,
                cols=request.cols,
                rows=request.rows,
                shell=request.shell,
            )
            session.user_id = request.user_id
            session.output_callback = request.output_callback
            session.exit_callback = request.exit_callback
            session.busy_callback = request.busy_callback
            return session

        session, was_created = self._registry.create_if_absent(session_id, _spawn_session)
        if not was_created:
            raise ValidationError(f"Session {session_id} already exists.")
        try:
            session.read_task = spawn_tracked_task(
                run_pty_read_loop(
                    session=session,
                    registry=self._registry,
                    on_exit=self._handle_session_exit,
                    logger=self._logger,
                ),
                name=f"pty-read-{session_id}",
                logger=self._logger,
                cancellation_binder=self._cancellation_binder,
                cancellation_id=build_soai_id(
                    ("sys", "pty", "read", safe_or_hashed_segment(session_id)),
                ),
                owner="terminal_pty_read",
                finalizer_tracker=self._finalizer_tracker,
            )
            if sys.platform != "win32" and session.busy_callback:
                session.busy_poll_task = spawn_tracked_task(
                    run_pty_busy_poll_loop(
                        session=session,
                        registry=self._registry,
                        logger=self._logger,
                    ),
                    name=f"pty-busy-poll-{session_id}",
                    logger=self._logger,
                    cancellation_binder=self._cancellation_binder,
                    cancellation_id=build_soai_id(
                        ("sys", "pty", "busy_poll", safe_or_hashed_segment(session_id)),
                    ),
                    owner="terminal_pty_busy_poll",
                    finalizer_tracker=self._finalizer_tracker,
                )
        except asyncio.CancelledError:
            await self._rollback_failed_session_creation(session)
            raise
        except PTY_SESSION_OPERATION_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="terminal.pty_session_manager.create_session",
            )
            log_exception(
                self._logger,
                coerced,
                message="Failed to create PTY session",
                operation=OPERATION_TERMINAL_PTY_SESSION_MANAGER_CREATE_SESSION,
                details={"session_id": session_id},
            )
            await self._rollback_failed_session_creation(session)
            raise coerced from exception
        except Exception as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="terminal.pty_session_manager.create_session",
            )
            log_exception(
                self._logger,
                coerced,
                message="Failed to create PTY session",
                operation=OPERATION_TERMINAL_PTY_SESSION_MANAGER_CREATE_SESSION,
                details={"session_id": session_id},
            )
            await self._rollback_failed_session_creation(session)
            raise coerced from exception
        self._logger.info(
            "PTY session created: %s (shell=%s, pid=%s, %sx%s)",
            session_id,
            truncate_shell_command(session.shell_path),
            session.pid,
            session.cols,
            session.rows,
        )
        return {
            "session_id": session_id,
            "shell": session.shell_path,
            "cols": session.cols,
            "rows": session.rows,
            "pid": session.pid,
        }

    async def _rollback_failed_session_creation(self, session: PTYSession) -> None:
        session.closed = True
        await cancel_and_await_task(session.read_task)
        session.read_task = None
        await cancel_and_await_task(session.busy_poll_task)
        session.busy_poll_task = None
        await self._io_handler.close_resources(session)
        await self._registry.unregister(session.session_id)

    async def write_input(self, session_id: str, data: bytes) -> None:
        session = require_live_session(self._registry, session_id)
        await self._io_handler.write_input(session, data)

    async def resize(self, session_id: str, cols: int, rows: int) -> None:
        session = require_live_session(self._registry, session_id)
        await self._io_handler.resize(session, cols, rows)
        log_terminal_trace(self._logger, f"PTY session {session_id} resized to {cols}x{rows}")

    async def close_session(self, session_id: str) -> None:
        session = self._registry.get(session_id)
        if not session:
            return
        async with session.cleanup_lock:
            if self._registry.get(session_id) is not session:
                return
            session.closed = True
            await cancel_and_await_task(session.read_task)
            session.read_task = None
            await cancel_and_await_task(session.busy_poll_task)
            session.busy_poll_task = None
            await self._io_handler.close_resources(session)
            await self._registry.unregister(session_id)
            self._logger.info("PTY session closed: %s", session_id)

    async def close_sessions_for_user(self, user_id: int) -> int:
        session_ids = self._registry.get_ids_for_user(user_id)
        closed_count = 0
        for session_id in session_ids:
            await self.close_session(session_id)
            closed_count += 1
        return closed_count

    async def shutdown(self) -> None:
        self._logger.debug("PTY session manager shutting down.")
        session_ids = self._registry.get_all_ids()
        failed_session_ids: list[str] = []
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                failed_session_ids.append(session_id)
                log_exception(
                    self._logger,
                    exception,
                    message="Error closing PTY session during shutdown.",
                    operation=OPERATION_TERMINAL_PTY_SESSION_MANAGER_SHUTDOWN,
                    details={"session_id": session_id},
                    level="warning",
                )
        if failed_session_ids:
            raise StateError(
                "PTY shutdown failed to close all sessions.",
                operation=OPERATION_TERMINAL_PTY_SESSION_MANAGER_SHUTDOWN,
                details={"session_ids": failed_session_ids},
            )

    async def _handle_session_exit(self, session_id: str, exit_code: int) -> None:
        _ = exit_code
        session = self._registry.get(session_id)
        if not session:
            return
        async with session.cleanup_lock:
            if self._registry.get(session_id) is not session:
                return
            session.closed = True
            await cancel_and_await_task(session.busy_poll_task)
            session.busy_poll_task = None
            await self._io_handler.close_resources(session)
            await self._registry.unregister(session_id)
            log_terminal_trace(self._logger, f"Exited PTY session cleaned up: {session_id}")
