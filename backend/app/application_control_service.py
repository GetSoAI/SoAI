"""SoAI - API-facing application control service [backend/app/application_control_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationLogging
from app.internal_protocols import (
    ApplicationRuntimeCoordinatorViewProtocol,
    ApplicationUpdateServiceProtocol,
)
from app.lifecycle.signals import initiate_shutdown_signal, request_runtime_restart
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.runtime.process_exit_deadline import ProcessExitDeadline
from core.runtime.protocols import RuntimeStateStoreProtocol

if TYPE_CHECKING:
    from core.app.protocols import ApplicationUpdateOutcome
    from core.types.json import JSONDict

__all__ = ("ApplicationControlService", "ApplicationControlServiceDependencies")


@dataclass(frozen=True, slots=True)
class ApplicationControlServiceDependencies:
    logging: ApplicationLogging
    runtime: RuntimeStateStoreProtocol
    services: ApplicationServices
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    update_service: ApplicationUpdateServiceProtocol
    process_exit_deadline: ProcessExitDeadline

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationControlServiceDependencies",
            logging=self.logging,
            runtime=self.runtime,
            runtime_coordinator=self.runtime_coordinator,
            services=self.services,
            update_service=self.update_service,
            process_exit_deadline=self.process_exit_deadline,
        )


class ApplicationControlService:
    def __init__(self, deps: ApplicationControlServiceDependencies) -> None:
        self._deps = deps

    async def update(self) -> tuple[ApplicationUpdateOutcome, str]:
        return await self._deps.update_service.update()

    async def get_update_preparation_status(self) -> JSONDict:
        return await self._deps.update_service.get_preparation_status()

    async def get_update_notice(self, user_id: int) -> JSONDict | None:
        return await self._deps.update_service.get_update_notice(user_id)

    async def acknowledge_update_notice(self, *, user_id: int, task_id: str) -> bool:
        return await self._deps.update_service.acknowledge_update_notice(
            user_id=user_id, task_id=task_id
        )

    def restart(self) -> bool:
        result = request_runtime_restart(
            self._deps.runtime,
            self._deps.logging.lifecycle_logger,
            config=self._deps.services.configuration.config,
            process_exit_deadline=self._deps.process_exit_deadline,
        )
        if not result:
            return False
        if self._deps.services.infrastructure.metrics_manager is not None:
            self._deps.services.infrastructure.metrics_manager.increment_counter(
                "global",
                "restarts_triggered",
            )
        return True

    def request_shutdown(self, reason: str | None = None) -> bool:
        result = initiate_shutdown_signal(
            self._deps.runtime.shutdown_event,
            self._deps.runtime.system_stop_event,
            self._deps.runtime.async_loop,
            reason,
            self._deps.logging.lifecycle_logger,
            self._deps.runtime.is_shutting_down,
            config=self._deps.services.configuration.config,
            process_exit_deadline=self._deps.process_exit_deadline,
        )
        if result:
            self._deps.runtime.set_manual_shutdown_requested()
        return result

    def schedule_background_task(
        self,
        coroutine: Coroutine[None, None, None],
        *,
        name: str | None = None,
    ) -> asyncio.Task[None] | None:
        return self._deps.runtime_coordinator.schedule_background_task(coroutine, name=name)

    def track_background_task(self, task: asyncio.Task[None]) -> None:
        if self._deps.runtime.is_shutting_down:
            self._deps.logging.logger.debug(
                "Tracking background task during shutdown may delay exit.",
            )
        self._deps.runtime_coordinator.track_background_task(task)
