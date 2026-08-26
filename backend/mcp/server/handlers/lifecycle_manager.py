"""SoAI - MCP server startup and shutdown lifecycle coordination [backend/mcp/server/handlers/lifecycle_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_mcp import MCPServerStartedEvent
from core.events.types_tasks import TaskProgressEvent
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.asyncio_task_spawner import create_tracked_and_track_task
from core.tasks.task_cancellation import cancel
from core.tasks.type_catalog import (
    TASK_TYPE_MCP_ELICITATION,
    TASK_TYPE_MCP_SAMPLING,
    TASK_TYPE_MCP_TOOL_CALL,
)
from mcp.server.handlers.host_interaction_expiry import run_host_interaction_expiry_loop
from mcp.server.handlers.lifecycle_cleanup import (
    cancel_background_tasks_safely,
    close_all_sessions_safely,
    reset_server_shutdown_event,
    shutdown_rag_safely,
    shutdown_utility_tools_safely,
)
from mcp.server.handlers.lifecycle_dependencies import MCPLifecycleManagerDependencies
from mcp.server.handlers.lifecycle_progress import handle_task_progress_event
from mcp.server.handlers.lifecycle_startup import (
    activate_server_mode_and_initialize_rag,
    setup_mcp_rag_state,
)

__all__ = ("MCPLifecycleManager",)

OPERATION_MCP_SERVER_LIFECYCLE_MANAGER_START = "mcp.server.lifecycle_manager.start"


LOGGER_NAME = "SoAI.mcp.server.lifecycle_manager"
OPERATION = "mcp.server.lifecycle_manager.shutdown.cancel_tasks"


class MCPLifecycleManager:
    def __init__(self, deps: MCPLifecycleManagerDependencies) -> None:
        self._deps = deps
        self._state = deps.state
        self._task_progress_subscribed = False
        self._started = False
        self._lifecycle_lock = asyncio.Lock()

    def _reset_start_state(self) -> None:
        reset_server_shutdown_event(self._state)

    def _subscribe_task_progress(self) -> None:
        if self._task_progress_subscribed or (not self._deps.tasks_enabled):
            return
        self._deps.event_bus.subscribe(
            TaskProgressEvent,
            self.on_task_progress_event,
        )
        self._task_progress_subscribed = True

    def _unsubscribe_task_progress(self) -> None:
        if not self._task_progress_subscribed:
            return
        self._deps.event_bus.unsubscribe(
            TaskProgressEvent,
            self.on_task_progress_event,
        )
        self._task_progress_subscribed = False

    async def start(self) -> None:
        async with self._lifecycle_lock:
            await self._start_locked()

    async def _start_locked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if not self._deps.enabled:
            logger.info("MCP integration is disabled.")
            return
        if self._started:
            logger.debug("MCPServer start requested while already running; ignoring.")
            return
        needs_task_registry = self._deps.tasks_enabled or (
            self._deps.rag_enabled and self._deps.http_client is not None
        )
        if needs_task_registry and self._deps.task_registry is None:
            raise StateError("Task registry is required for MCP tasks or RAG operations.")
        self._reset_start_state()
        self._state.server_mode_active = False
        self._state.rag_resource_patterns = {}
        self._state.mcp_rag = None
        try:
            if self._deps.mcp_search:
                await self._deps.load_search_api_keys()
            setup_mcp_rag_state(self._deps)
            server_mode_active = await activate_server_mode_and_initialize_rag(
                self._deps,
                logger=logger,
            )
            if server_mode_active:
                self._subscribe_task_progress()
            if self._deps.tasks_enabled:
                logger.debug(
                    "MCP Tasks feature enabled with TTL=%ds, max_concurrent=%d",
                    self._deps.tasks_default_ttl_sec,
                    self._deps.tasks_max_concurrent_per_client,
                )
            _ = await create_tracked_and_track_task(
                self._deps.session_cleanup_loop(self._deps.session_sweep_interval_sec),
                cancellation_binder=self._deps.cancellation_binder,
                cancellation_id=build_soai_id(("sys", "mcp", "session_cleanup")),
                owner="mcp_session_cleanup",
                track_task=self._deps.track_background_task,
                name="mcp-session-cleanup",
                logger=logger,
            )
            if self._deps.tasks_enabled:
                _ = await create_tracked_and_track_task(
                    run_host_interaction_expiry_loop(
                        shutdown_event=self._state.shutdown_event,
                        task_registry_queries=self._deps.task_registry_queries,
                        server_ref=self._deps.server_ref,
                        remote=self._deps.mcp_remote,
                        logger=logger,
                        timeout_ms=self._deps.user_interaction_timeout_ms,
                    ),
                    cancellation_binder=self._deps.cancellation_binder,
                    cancellation_id=build_soai_id(("sys", "mcp", "host_interaction_expiry")),
                    owner="mcp_host_interaction_expiry",
                    track_task=self._deps.track_background_task,
                    name="mcp-host-interaction-expiry",
                    logger=logger,
                )
            await self._deps.event_bus.publish(MCPServerStartedEvent())
        except asyncio.CancelledError:
            await self._rollback_failed_start()
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            operation = "mcp.server.lifecycle_manager.start"
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                logger,
                coerced,
                message="MCPServer startup failed; rolling back.",
                operation=OPERATION_MCP_SERVER_LIFECYCLE_MANAGER_START,
                details={},
            )
            await self._rollback_failed_start()
            raise
        self._started = True
        logger.info("MCPServer started successfully.")

    async def _rollback_failed_start(self) -> None:
        self._unsubscribe_task_progress()
        self._state.server_mode_active = False
        await cancel_background_tasks_safely(
            self._deps.background_tasks,
            message="Cancelling MCP background tasks after startup failure...",
            operation="mcp.server.lifecycle_manager.start.rollback.cancel_background_tasks",
        )
        await close_all_sessions_safely(
            self._deps.close_all_sessions,
            operation="mcp.server.lifecycle_manager.start.rollback.close_sessions",
            message="Failed to close MCP sessions during startup rollback.",
        )
        await shutdown_rag_safely(
            self._state,
            operation="mcp.server.lifecycle_manager.start.rollback.shutdown_rag",
            message="Failed to shut down MCP RAG during startup rollback.",
        )
        self._state.rag_resource_patterns = {}
        self._started = False

    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            await self._shutdown_locked()

    async def _shutdown_locked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._state.shutdown_event.is_set() and (not self._started):
            return
        logger.debug("MCPServer shutdown initiated.")
        self._state.shutdown_event.set()
        self._state.server_mode_active = False
        self._started = False
        try:
            try:
                for task_type in (
                    TASK_TYPE_MCP_TOOL_CALL,
                    TASK_TYPE_MCP_SAMPLING,
                    TASK_TYPE_MCP_ELICITATION,
                ):
                    for task in await self._deps.task_registry_queries.query_active(
                        task_type=task_type,
                        limit=10000,
                    ):
                        if task.owner_type == "mcp_client" and not task.status.is_terminal():
                            await cancel(
                                self._deps.task_registry,
                                task.task_id,
                                reason="MCP Manager shutdown",
                            )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to cancel active MCP tasks during shutdown.",
                    operation=OPERATION,
                    level="warning",
                )
        finally:
            self._unsubscribe_task_progress()
            await close_all_sessions_safely(
                self._deps.close_all_sessions,
                operation="mcp.server.lifecycle_manager.shutdown.close_sessions",
                message="Failed to close MCP sessions during shutdown.",
            )
            await cancel_background_tasks_safely(
                self._deps.background_tasks,
                message=(
                    f"Cancelling {self._deps.background_tasks.pending()} " "MCP background tasks..."
                ),
                operation="mcp.server.lifecycle_manager.shutdown.cancel_background_tasks",
            )
            await shutdown_rag_safely(
                self._state,
                operation="mcp.server.lifecycle_manager.shutdown.rag",
                message="Failed to shut down MCP RAG during shutdown.",
            )
            await shutdown_utility_tools_safely(
                self._state,
                operation="mcp.server.lifecycle_manager.shutdown.utility_tools",
            )
            self._deps.rag_chunker.shutdown()
            self._state.rag_resource_patterns = {}
            logger.debug("MCPServer has been shut down.")

    async def on_task_progress_event(self, event: Event) -> None:
        if not isinstance(event, TaskProgressEvent):
            return
        await handle_task_progress_event(
            state=self._state,
            task_registry=self._deps.task_registry,
            tasks_enabled=self._deps.tasks_enabled,
            event=event,
        )
