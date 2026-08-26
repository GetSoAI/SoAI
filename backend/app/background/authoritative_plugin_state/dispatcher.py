"""SoAI - Durable authoritative plugin state outbox dispatcher [backend/app/background/authoritative_plugin_state/dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.background.authoritative_plugin_state.outbox.failures import (
    AuthoritativePluginStateOutboxFailureRecorder,
)
from app.background.authoritative_plugin_state.outbox.processor import (
    AuthoritativePluginStateOutboxProcessor,
)
from app.background.authoritative_plugin_state.outbox.transitions import (
    AuthoritativePluginStateOutboxTransitionController,
)
from app.background.authoritative_plugin_state.waiters import (
    AuthoritativePluginStateWaiters,
)
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.config.clamped_numeric import require_positive_numeric_config
from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from core.timing.constants import MODERATE_DELAY_SEC
from core.timing.epoch import epoch_ms
from database.repositories.plugins.authoritative_state_outbox_claims import (
    sync_claim_authoritative_state_events_for_shutdown,
    sync_claim_pending_authoritative_state_events,
    sync_count_unpublished_authoritative_state_events,
)

__all__ = (
    "AuthoritativePluginStateDispatcher",
    "AuthoritativePluginStateDispatcherDependencies",
)

LOGGER_NAME = "SoAI.app.background.dispatcher"
OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_CLAIM = (
    "authoritative_plugin_state.dispatcher.claim"
)
OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_SHUTDOWN_DRAIN_CLAIM = (
    "authoritative_plugin_state.dispatcher.shutdown_drain.claim"
)
OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_SHUTDOWN_DRAIN_COUNT = (
    "authoritative_plugin_state.dispatcher.shutdown_drain.count"
)


_DISPATCHER_BATCH_LIMIT = 16
_DISPATCHER_PROCESSING_TIMEOUT_MS = 120000
_DISPATCHER_SHUTDOWN_DRAIN_TIMEOUT_SEC = 18.0
_DISPATCHER_SHUTDOWN_DRAIN_SLEEP_SEC = 0.05
_DISPATCHER_SHUTDOWN_BATCH_LIMIT = 256


@dataclass(frozen=True, slots=True)
class AuthoritativePluginStateDispatcherDependencies:
    config: ConfigProtocol
    database_core: DatabaseCoreProtocol
    event_bus: EventBusProtocol
    waiters: AuthoritativePluginStateWaiters
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AuthoritativePluginStateDispatcherDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_core=self.database_core,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            waiters=self.waiters,
        )


class AuthoritativePluginStateDispatcher:
    def __init__(self, deps: AuthoritativePluginStateDispatcherDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._failure_recorder = AuthoritativePluginStateOutboxFailureRecorder(
            self._deps.database_core.writer,
            logger=self._logger,
        )
        self._transition_controller = AuthoritativePluginStateOutboxTransitionController(
            self._deps.database_core.writer,
            logger=self._logger,
        )
        self._processor = AuthoritativePluginStateOutboxProcessor(
            event_bus=self._deps.event_bus,
            waiters=self._deps.waiters,
            failure_recorder=self._failure_recorder,
            transition_controller=self._transition_controller,
            logger=self._logger,
        )

    async def start(self) -> None:
        if self._task is not None and (not self._task.done()):
            return
        self._shutdown_event = asyncio.Event()
        self._processor.reset()

        async def _run_loop() -> None:
            while not self._shutdown_event.is_set():
                await self._drain_once()
                if self._shutdown_event.is_set():
                    break
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=MODERATE_DELAY_SEC,
                    )
                except TimeoutError:
                    continue

        self._task = spawn_supervised_tracked_task(
            _run_loop,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="plugin_authoritative_state_outbox",
                owner="dispatch",
                include_random_suffix=False,
            ),
            owner="authoritative_plugin_state_dispatcher",
            name="authoritative-plugin-state-dispatcher",
            logger=self._logger,
            metadata={
                "batch_limit": _DISPATCHER_BATCH_LIMIT,
                "processing_timeout_ms": _DISPATCHER_PROCESSING_TIMEOUT_MS,
            },
            restart_initial_delay_sec=0.5,
            restart_max_delay_sec=10.0,
            restart_jitter_sec=0.5,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        if self._task is not None:
            await await_background_task_shutdown(
                self._task,
                logger=self._logger,
                operation="authoritative_plugin_state_dispatcher.shutdown",
                message="Authoritative plugin state dispatcher failed during shutdown (non-critical).",
            )
            self._task = None
        if self._deps.database_core.writer.is_initialized:
            await self._drain_outbox_until_empty(
                deadline=deadline_after(self._resolve_shutdown_drain_timeout_sec()),
            )
        await self._deps.waiters.resolve_shutdown()

    def _resolve_shutdown_drain_timeout_sec(self) -> float:
        timeout_key = "PLUGINS.AUTHORITATIVE_STATE.OUTBOX.SHUTDOWN_DRAIN_TIMEOUT_SEC"
        raw_timeout = self._deps.config.get(
            timeout_key,
            _DISPATCHER_SHUTDOWN_DRAIN_TIMEOUT_SEC,
        )
        return require_positive_numeric_config(
            raw_timeout,
            key=timeout_key,
            build_error=ValueError,
        )

    async def _drain_outbox_until_empty(self, *, deadline: MonotonicDeadline) -> None:
        while not deadline.expired():
            await self._processor.flush_pending_updates(now_ms=epoch_ms())
            try:
                remaining = await self._deps.database_core.writer.queue_write_operation(
                    sync_count_unpublished_authoritative_state_events,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to count authoritative plugin state outbox rows during shutdown drain.",
                    operation=OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_SHUTDOWN_DRAIN_COUNT,
                    level="warning",
                )
                await asyncio.sleep(_DISPATCHER_SHUTDOWN_DRAIN_SLEEP_SEC)
                continue
            if not isinstance(remaining, int):
                remaining = 0
            if remaining <= 0:
                return
            try:
                claimed_rows = await self._deps.database_core.writer.queue_write_operation(
                    sync_claim_authoritative_state_events_for_shutdown,
                    epoch_ms(),
                    _DISPATCHER_SHUTDOWN_BATCH_LIMIT,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to claim authoritative plugin state outbox rows during shutdown drain.",
                    operation=OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_SHUTDOWN_DRAIN_CLAIM,
                    level="warning",
                )
                await asyncio.sleep(_DISPATCHER_SHUTDOWN_DRAIN_SLEEP_SEC)
                continue
            if not claimed_rows:
                await asyncio.sleep(_DISPATCHER_SHUTDOWN_DRAIN_SLEEP_SEC)
                continue
            for row in claimed_rows:
                await self._processor.process_row(row)
        await self._processor.flush_pending_updates(now_ms=epoch_ms())

    async def _drain_once(self) -> None:
        await self._processor.flush_pending_updates(now_ms=epoch_ms())
        try:
            claimed_rows = await self._deps.database_core.writer.queue_write_operation(
                sync_claim_pending_authoritative_state_events,
                epoch_ms(),
                _DISPATCHER_BATCH_LIMIT,
                _DISPATCHER_PROCESSING_TIMEOUT_MS,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to claim authoritative plugin state outbox rows.",
                operation=OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_CLAIM,
                level="warning",
            )
            return
        if not claimed_rows:
            return
        for row in claimed_rows:
            await self._processor.process_row(row)
