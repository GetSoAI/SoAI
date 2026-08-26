"""SoAI - Startup persistence activation after initial user creation [backend/app/startup_steps/initial_user_persistence_activation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.app.protocols import ApplicationRuntimeCoordinatorProtocol
from core.auth.protocols_database_tokens import DatabaseTokensProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_webui import UserCreatedEvent
from core.hardware.protocols import HardwareGpuTuningProtocol, HardwareManagerProtocol
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.protocols import RuntimeStateStoreProtocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = (
    "InitialUserPersistenceActivation",
    "InitialUserPersistenceActivationDependencies",
    "prune_expired_webui_session_state",
    "schedule_prune_webui_session_state",
)

OPERATION_APPLICATION_STARTUP_PRUNE_WEBUI_SESSION_STATE = (
    "application_startup.prune_webui_session_state"
)
OPERATION_STARTUP_INITIAL_USER_PERSISTENCE_ACTIVATION = (
    "startup.initial_user_persistence_activation"
)


@dataclass(frozen=True, slots=True)
class InitialUserPersistenceActivationDependencies:
    event_bus: EventBusProtocol
    runtime_coordinator: ApplicationRuntimeCoordinatorProtocol
    metrics_manager: MetricsManagerProtocol
    hardware_manager: HardwareManagerProtocol
    hardware_gpu_tuning: HardwareGpuTuningProtocol
    database_tokens: DatabaseTokensProtocol
    runtime_state: RuntimeStateStoreProtocol
    logger: LoggerProtocol
    hardware_activation_enabled: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="InitialUserPersistenceActivationDependencies",
            database_tokens=self.database_tokens,
            event_bus=self.event_bus,
            hardware_activation_enabled=self.hardware_activation_enabled,
            hardware_gpu_tuning=self.hardware_gpu_tuning,
            hardware_manager=self.hardware_manager,
            logger=self.logger,
            metrics_manager=self.metrics_manager,
            runtime_coordinator=self.runtime_coordinator,
            runtime_state=self.runtime_state,
        )


async def prune_expired_webui_session_state(
    database_tokens: DatabaseTokensProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        await database_tokens.prune_expired_webui_session_state()
        logger.debug("Pruned expired WebUI session state from the database.")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error while pruning expired WebUI session state.",
            operation=OPERATION_APPLICATION_STARTUP_PRUNE_WEBUI_SESSION_STATE,
        )


def schedule_prune_webui_session_state(
    runtime_coordinator: ApplicationRuntimeCoordinatorProtocol,
    runtime_state: RuntimeStateStoreProtocol,
    database_tokens: DatabaseTokensProtocol,
    logger: LoggerProtocol,
) -> None:
    task_coroutine = prune_expired_webui_session_state(database_tokens, logger)
    scheduled_task = runtime_coordinator.schedule_background_task(
        task_coroutine,
        name="prune-webui-session-state",
    )
    runtime_state.set_prune_tokens_task(scheduled_task)


class InitialUserPersistenceActivation:

    def __init__(self, deps: InitialUserPersistenceActivationDependencies) -> None:
        self._deps = deps
        self._enabled = False
        self._activated = False
        self._activation_lock = asyncio.Lock()
        self._handler: Callable[[Event], Awaitable[None]] = self._handle_user_created_event

    def enable(self) -> None:
        if self._enabled:
            return
        self._deps.event_bus.subscribe(UserCreatedEvent, self._handler)
        self._enabled = True

    async def _handle_user_created_event(self, event: Event) -> None:
        if not isinstance(event, UserCreatedEvent):
            return
        if event.user_id <= 0:
            return
        async with self._activation_lock:
            if self._activated:
                return
            try:
                await self._deps.metrics_manager.start()
                schedule_prune_webui_session_state(
                    runtime_coordinator=self._deps.runtime_coordinator,
                    runtime_state=self._deps.runtime_state,
                    database_tokens=self._deps.database_tokens,
                    logger=self._deps.logger,
                )
                if self._deps.hardware_activation_enabled:
                    await self._deps.hardware_manager.start_monitoring()
                    await self._deps.hardware_gpu_tuning.apply_startup_gpu_settings()
                self._deps.event_bus.unsubscribe(UserCreatedEvent, self._handler)
                self._activated = True
                self._deps.logger.info(
                    "Startup persistence services activated after initial user creation.",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._deps.logger,
                    exception,
                    message="Failed to activate startup persistence services after user creation. Services will be retried on next user creation event or startup tick.",
                    operation=OPERATION_STARTUP_INITIAL_USER_PERSISTENCE_ACTIVATION,
                )
