"""SoAI - Application lifecycle shutdown service [backend/app/lifecycle_shutdown_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.application_dependencies import ApplicationLogging
from app.composition.shutdown_reconciliation import reconcile_runtime_state_on_shutdown
from app.internal_protocols import (
    ApplicationHostServiceProtocol,
    ApplicationRuntimeCoordinatorViewProtocol,
)
from app.lifecycle.budgets import (
    LifecycleShutdownBudgets,
    resolve_lifecycle_shutdown_budgets,
)
from app.types_application import ApplicationContext
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.events.types_system import SoAIMainState, SystemQuiesceEvent
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.runtime.shutdown_marker import (
    clear_process_shutdown_marker,
    resolve_process_shutdown_marker_path,
)
from features.api.middleware.quiesce import await_quiesce_request_drain

__all__ = ("LifecycleShutdownService", "LifecycleShutdownServiceDependencies")

OPERATION_LIFECYCLE_SHUTDOWN = "app.lifecycle_shutdown_service.shutdown"


@dataclass(frozen=True, slots=True)
class LifecycleShutdownServiceDependencies:
    logging: ApplicationLogging
    runtime: RuntimeStateStoreProtocol
    services: ApplicationServices
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    host_service: ApplicationHostServiceProtocol
    run_shutdown_sequence: Callable[[ApplicationContext, LifecycleShutdownBudgets], Awaitable[None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleShutdownServiceDependencies",
            host_service=self.host_service,
            logging=self.logging,
            runtime=self.runtime,
            runtime_coordinator=self.runtime_coordinator,
            run_shutdown_sequence=self.run_shutdown_sequence,
            services=self.services,
        )


class LifecycleShutdownService:
    def __init__(self, deps: LifecycleShutdownServiceDependencies) -> None:
        self._deps = deps

    async def shutdown(self, application_context: ApplicationContext) -> None:
        if not self._deps.runtime.begin_shutdown():
            return
        shutdown_start_time = time.monotonic()
        self._deps.logging.logger.info("--- Shutting down SoAI ---")
        banner_system = self._deps.runtime_coordinator.ensure_banner_system()
        if self._deps.runtime.critical_shutdown_reason or self._deps.runtime.exit_code != 0:
            banner_system.emit("failure_shutdown")
            if self._deps.runtime.critical_shutdown_reason:
                self._deps.logging.logger.critical(self._deps.runtime.critical_shutdown_reason)
        elif self._deps.runtime.manual_shutdown_requested:
            banner_system.emit("manual_shutdown")
        elif self._deps.runtime.restart_requested:
            banner_system.emit("restart")
        else:
            banner_system.emit("shutdown")
        await self._clear_restart_requirement_before_shutdown()
        self._deps.runtime.set_shutdown_requested()
        await self._publish_stopping_state()
        if not self._deps.runtime.system_stop_event.is_set():
            self._deps.runtime.set_system_stop()
        try:
            budgets = resolve_lifecycle_shutdown_budgets(self._deps.services.configuration.config)
            await self._publish_quiesce_event()
            await self._drain_api_requests(budgets.quiesce_period_sec)
            await self._deps.host_service.shutdown_servers(budgets.server_drain_timeout_sec)
            await self._deps.host_service.stop_discovery_server()
            if self._deps.services.databases.core.writer.is_initialized:
                await self._quiesce_database_dispatchers_before_reconciliation()
                await self._reconcile_runtime_state_before_teardown()
            await self._deps.run_shutdown_sequence(application_context, budgets)
            await self._clear_process_shutdown_marker()
        finally:
            self._deps.logging.logger.info(
                "--- SoAI shutdown complete in %.2fs ---",
                time.monotonic() - shutdown_start_time,
            )

    async def _clear_process_shutdown_marker(self) -> None:
        config = self._deps.services.configuration.config
        system_data_path = config.get_str("SYSTEM.PATHS.SYSTEM_DATA")
        if not system_data_path:
            return
        await clear_process_shutdown_marker(
            resolve_process_shutdown_marker_path(system_data_path),
            self._deps.logging.lifecycle_logger,
        )

    async def _reconcile_runtime_state_before_teardown(self) -> None:
        databases = self._deps.services.databases
        try:
            await reconcile_runtime_state_on_shutdown(
                database_agent_turn_process_boundary=databases.agent_turn_process_boundary,
                database_agent_turns=databases.agent_turns,
                database_tool_calls=databases.tool_calls,
                database_automation_run_scheduler=databases.automation_run_scheduler,
                logger=self._deps.logging.logger,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Runtime shutdown reconciliation failed; continuing teardown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )
        except SoAIError as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Runtime shutdown reconciliation failed; continuing teardown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
            )
            log_exception(
                self._deps.logging.logger,
                coerced,
                message="Unexpected runtime shutdown reconciliation failure; continuing teardown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )

    async def _quiesce_database_dispatchers_before_reconciliation(self) -> None:
        infrastructure = self._deps.services.infrastructure
        for component_name, dispatcher in (
            (
                "Mutation Command Supervisor",
                infrastructure.mutation_command_supervisor,
            ),
            (
                "Authoritative Plugin State Dispatcher",
                infrastructure.authoritative_plugin_state_dispatcher,
            ),
            ("Domain Event Outbox Dispatcher", infrastructure.domain_event_outbox_dispatcher),
        ):
            try:
                await dispatcher.shutdown()
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._deps.logging.logger,
                    exception,
                    message=f"{component_name} quiesce before reconciliation failed.",
                    operation=OPERATION_LIFECYCLE_SHUTDOWN,
                    level="warning",
                )
            except SoAIError as exception:
                log_exception(
                    self._deps.logging.logger,
                    exception,
                    message=f"{component_name} quiesce before reconciliation failed.",
                    operation=OPERATION_LIFECYCLE_SHUTDOWN,
                    level="warning",
                )
            except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_LIFECYCLE_SHUTDOWN,
                )
                log_exception(
                    self._deps.logging.logger,
                    coerced,
                    message=f"Unexpected {component_name} quiesce failure before reconciliation.",
                    operation=OPERATION_LIFECYCLE_SHUTDOWN,
                    level="warning",
                )

    async def _clear_restart_requirement_before_shutdown(self) -> None:
        if not self._deps.runtime.restart_state_manager or self._deps.runtime.restart_requested:
            return
        try:
            await self._deps.runtime.restart_state_manager.clear_restart_requirement(
                "shutdown_without_restart",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Failed to clear restart requirement during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
            )
            log_exception(
                self._deps.logging.logger,
                coerced,
                message="Unexpected restart requirement clear failure during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )

    async def _publish_stopping_state(self) -> None:
        try:
            await self._deps.services.infrastructure.state_aggregator.set_main_state(
                SoAIMainState.STOPPING,
                "shutdown_initiated",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Failed to publish STOPPING state during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
            )
            log_exception(
                self._deps.logging.logger,
                coerced,
                message="Unexpected STOPPING state publication failure during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )

    async def _publish_quiesce_event(self) -> None:
        event_bus = self._deps.services.infrastructure.event_bus
        if event_bus.shutdown_event.is_set():
            return
        try:
            await event_bus.publish(SystemQuiesceEvent())
        except StateError:
            self._deps.logging.logger.debug(
                "SystemQuiesceEvent could not be published (event bus shutdown race).",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="SystemQuiesceEvent publication failed during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
            )
            log_exception(
                self._deps.logging.logger,
                coerced,
                message="Unexpected SystemQuiesceEvent publication failure during shutdown.",
                operation=OPERATION_LIFECYCLE_SHUTDOWN,
                level="warning",
            )

    async def _drain_api_requests(self, timeout_sec: float) -> None:
        drained = await await_quiesce_request_drain(
            self._deps.runtime.fastapi_app,
            timeout_sec,
        )
        if drained:
            return
        self._deps.logging.logger.warning(
            "API request drain did not complete within %.1fs before server shutdown.",
            timeout_sec,
        )
