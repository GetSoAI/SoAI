"""SoAI - Background shell-session watch service [backend/mcp/tools/shell_background/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, override

from core.concurrency.cancellation_cleanup import (
    uncancel_and_wait,
    uncancel_then_cleanup,
)
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.execution.owned_execution_tasks import (
    create_owned_execution_task,
    finalize_owned_execution_task,
    mark_owned_execution_running,
)
from core.mcp.protocols_main import ShellBackgroundServiceProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.monotonic import monotonic_ms
from core.tool_calls.deferred_tool_call_acceptance import (
    persist_deferred_tool_call_accepted_state,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
)
from mcp.tools.shell_background.dependencies import ShellBackgroundServiceDependencies
from mcp.tools.shell_background.owned_task_status import (
    resolve_owned_task_terminal_status,
)
from mcp.tools.shell_background.start_failure import (
    cleanup_cancelled_shell_background_start,
    cleanup_failed_shell_background_start,
)
from mcp.tools.shell_background.watch_factories import (
    build_shell_background_owned_task_metadata,
    build_shell_background_streamer_dependencies,
)
from mcp.tools.shell_background.watcher import (
    ShellBackgroundWatch,
    run_background_shell_watch,
)
from mcp.tools.shell_session_cleanup import ShellSessionCleanupDeps

if TYPE_CHECKING:
    from core.terminal.protocols import TerminalServiceProtocol
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionStoreProtocol

__all__ = (
    "ShellBackgroundService",
    "ShellBackgroundServiceDependencies",
)

OWNER = "mcp.shell"
OPERATION_SHELL_BACKGROUND_RUN = "mcp.tools.shell_background.service.run_owned_watch"


class ShellBackgroundService(ShellBackgroundServiceProtocol):
    def __init__(self, deps: ShellBackgroundServiceDependencies) -> None:
        self._database_tool_calls = deps.database_tool_calls
        self._task_registry = deps.task_registry
        self._event_bus = deps.event_bus
        self._task_cancellation_binder = deps.task_cancellation_binder
        self._task_finalizer_tracker = deps.task_finalizer_tracker
        self._logger = deps.logger
        self._active_watch_tasks: set[asyncio.Task[None]] = set()
        self._shutting_down: bool = False

    def _discard_watch_task(self, task: asyncio.Task[None]) -> None:
        self._active_watch_tasks.discard(task)

    @override
    async def shutdown(self) -> None:
        self._shutting_down = True
        pending = [task for task in self._active_watch_tasks if not task.done()]
        if not pending:
            return
        await cancel_and_await(
            pending,
            logger=self._logger,
            task_label="shell background watch task(s)",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )

    async def _run_owned_watch(self, *, watch: ShellBackgroundWatch, owner_task_id: str) -> None:
        try:
            await mark_owned_execution_running(
                self._task_registry,
                owner_task_id=owner_task_id,
                status_message="Running shell",
            )
            final_status = await run_background_shell_watch(watch)
        except asyncio.CancelledError:
            await uncancel_then_cleanup(
                finalize_owned_execution_task(
                    self._task_registry,
                    owner_task_id=owner_task_id,
                    final_status=TOOL_CALL_STATUS_CANCELLED,
                    status_message="Cancelled",
                    error_message="Shell cancelled.",
                ),
            )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SHELL_BACKGROUND_RUN,
            )
            log_exception(
                self._logger,
                coerced,
                message="Background shell watch task failed unexpectedly.",
                operation=OPERATION_SHELL_BACKGROUND_RUN,
                details={"owner_task_id": owner_task_id},
            )
            await uncancel_and_wait(
                finalize_owned_execution_task(
                    self._task_registry,
                    owner_task_id=owner_task_id,
                    final_status=TOOL_CALL_STATUS_ERROR,
                    status_message="Failed",
                    error_message=coerced.message,
                ),
            )
            return
        terminal_status = resolve_owned_task_terminal_status(final_status)
        await uncancel_and_wait(
            finalize_owned_execution_task(
                self._task_registry,
                owner_task_id=owner_task_id,
                final_status=final_status,
                status_message=terminal_status.status_message,
                error_message=terminal_status.error_message,
            ),
        )

    @override
    async def start_background_shell_watch(
        self,
        *,
        runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
        terminal: TerminalServiceProtocol,
        identity: CurrentToolCallIdentity,
        shell_session_id: int,
        terminal_session_id: str,
        tty: bool,
        max_output_chars: int,
        output_limit: int,
        trace_id: str,
        accepted_result: JSONValue,
    ) -> JSONDict:
        if self._shutting_down:
            raise StateError("Shell background service is shutting down.")
        cleanup_deps = ShellSessionCleanupDeps(
            runtime_sessions=runtime_sessions,
            terminal=terminal,
            logger=self._logger,
        )
        cancellation_id = f"shell-watch-{uuid.uuid4().hex}"
        owned_task = await create_owned_execution_task(
            self._task_registry,
            user_id=identity.user_id,
            owner_id=identity.conv_id,
            owner_type="conversation",
            cancellation_id=cancellation_id,
            owner_task_id=None,
            initial_status="queued",
            status_message="Accepted",
            metadata=build_shell_background_owned_task_metadata(
                identity=identity,
                shell_session_id=shell_session_id,
            ),
        )
        owned_task_finalized = False
        try:
            await persist_deferred_tool_call_accepted_state(
                database_tool_calls=self._database_tool_calls,
                storage_call_id=identity.storage_call_id,
                owner_task_id=owned_task.task_id,
                accepted_result=accepted_result,
            )
            session = runtime_sessions.get_shell_session(shell_session_id)
            if session is None:
                raise StateError("Shell background session disappeared before watcher start.")
            session.background_watch_started = True
            watch = ShellBackgroundWatch(
                streamer_deps=build_shell_background_streamer_dependencies(
                    database_tool_calls=self._database_tool_calls,
                    event_bus=self._event_bus,
                    identity=identity,
                    logger=self._logger,
                    trace_id=trace_id,
                ),
                runtime_sessions=runtime_sessions,
                terminal=terminal,
                identity=identity,
                shell_session_id=shell_session_id,
                terminal_session_id=terminal_session_id,
                tty=tty,
                max_output_chars=max_output_chars,
                output_limit=output_limit,
                started_ms=monotonic_ms(),
            )
            if self._shutting_down:
                await cleanup_cancelled_shell_background_start(
                    task_registry=self._task_registry,
                    database_tool_calls=self._database_tool_calls,
                    identity=identity,
                    cleanup_deps=cleanup_deps,
                    owner_task_id=owned_task.task_id,
                    shell_session_id=shell_session_id,
                    terminal_session_id=terminal_session_id,
                    error_message="Shell background service is shutting down.",
                )
                owned_task_finalized = True
                raise StateError("Shell background service is shutting down.")
            watch_task = spawn_tracked_task(
                self._run_owned_watch(watch=watch, owner_task_id=owned_task.task_id),
                name=f"shell-watch-{cancellation_id}",
                logger=self._logger,
                done_callback=self._discard_watch_task,
                cancellation_binder=self._task_cancellation_binder,
                cancellation_id=cancellation_id,
                owner=OWNER,
                metadata={"conv_id": identity.conv_id, "call_id": identity.call_id},
                finalizer_tracker=self._task_finalizer_tracker,
            )
        except asyncio.CancelledError:
            if not owned_task_finalized:
                await cleanup_cancelled_shell_background_start(
                    task_registry=self._task_registry,
                    database_tool_calls=self._database_tool_calls,
                    identity=identity,
                    cleanup_deps=cleanup_deps,
                    owner_task_id=owned_task.task_id,
                    shell_session_id=shell_session_id,
                    terminal_session_id=terminal_session_id,
                    error_message="Shell background watch start was cancelled.",
                )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS:
            if not owned_task_finalized:
                await cleanup_failed_shell_background_start(
                    task_registry=self._task_registry,
                    database_tool_calls=self._database_tool_calls,
                    identity=identity,
                    cleanup_deps=cleanup_deps,
                    owner_task_id=owned_task.task_id,
                    shell_session_id=shell_session_id,
                    terminal_session_id=terminal_session_id,
                )
            raise
        self._active_watch_tasks.add(watch_task)
        if watch_task.done():
            self._discard_watch_task(watch_task)
        return {
            "owner_task_id": owned_task.task_id,
            "cancellation_id": cancellation_id,
        }
