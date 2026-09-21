"""SoAI - Application controller and lifecycle composition [backend/app/application_controller.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application_control_service import (
    ApplicationControlService,
    ApplicationControlServiceDependencies,
)
from app.application_controller_services import (
    ApplicationControllerServicesDependencies,
    build_application_controller_services,
)
from app.application_host_instance import ApplicationHostInstance
from app.backup.restore_runtime_quiescence import (
    RestoreRuntimeQuiescence,
    RestoreRuntimeQuiescenceDependencies,
)
from app.runtime import ApplicationRuntimeCoordinator
from app.runtime_dependencies import ApplicationRuntimeCoordinatorDependencies
from app.types_application import ApplicationAssembly, ApplicationContext
from core.logging.trace import get_logger
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.timing.startup_timings import StartupTimingsRecorder
from features.api.runtime.power_operation_dispatch import (
    PowerOperationDispatcher,
    PowerOperationDispatcherDependencies,
)
from features.api.runtime.power_operation_events import (
    PowerOperationEventPublisher,
    PowerOperationEventPublisherDependencies,
)
from features.api.runtime.power_operation_supervisor import (
    PowerOperationSupervisor,
    PowerOperationSupervisorDependencies,
)

if TYPE_CHECKING:
    from core.app.protocols import ApplicationUpdateOutcome

__all__ = ("ApplicationController",)

LOGGER_NAME = "SoAI.app.application_controller"


class ApplicationController:
    def __init__(
        self,
        assembly: ApplicationAssembly,
        *,
        startup_timings: StartupTimingsRecorder,
    ) -> None:
        self._context = ApplicationContext(
            logging=assembly.logging,
            runtime=assembly.runtime,
            api_runtime_singletons=assembly.api_runtime_singletons,
            paths=assembly.paths,
            services=assembly.services,
            edition_composition=assembly.edition_composition,
        )
        self._startup_timings = startup_timings
        self._context.services.storage.backup_service.attach_restore_runtime_quiescence(
            RestoreRuntimeQuiescence(
                RestoreRuntimeQuiescenceDependencies(
                    application_context=self._context,
                    logger=get_logger(LOGGER_NAME),
                )
            )
        )
        module_dependencies = assembly.module_dependencies
        self._runtime_coordinator = ApplicationRuntimeCoordinator(
            ApplicationRuntimeCoordinatorDependencies(
                logging=self._context.logging,
                runtime_state=self._context.runtime,
                configuration=self._context.services.configuration.config,
                event_bus=self._context.services.infrastructure.event_bus,
                logging_manager=self._context.services.infrastructure.log_manager,
                http_client=self._context.services.infrastructure.http_client,
                runtime_flags=self._context.services.configuration.runtime_flags,
                module_dependencies=module_dependencies.runtime,
                finalizer_tracker=self._context.services.tasks.cancellation.finalizer_tracker,
                task_cancellation_binder=(self._context.services.tasks.cancellation.binder),
                core_routing_applicator=self._context.services.orchestrator.lifecycle.routing,
                update_plugin_worker_runtime_flags=self._update_plugin_worker_runtime_flags,
            ),
        )
        self._controller_services = build_application_controller_services(
            ApplicationControllerServicesDependencies(
                logging=self._context.logging,
                paths=self._context.paths,
                runtime=self._context.runtime,
                services=self._context.services,
                module_dependencies=module_dependencies,
                runtime_coordinator=self._runtime_coordinator,
                startup_timings=self._startup_timings,
                request_restart=self.restart,
                edition_composition=assembly.edition_composition,
            ),
        )
        self._application_control = ApplicationControlService(
            ApplicationControlServiceDependencies(
                logging=self._context.logging,
                runtime=self._context.runtime,
                services=self._context.services,
                runtime_coordinator=self._runtime_coordinator,
                update_service=self._controller_services.update,
            ),
        )
        power_dispatcher = PowerOperationDispatcher(
            PowerOperationDispatcherDependencies(
                application_control=self._application_control,
                runtime_flags=self._context.services.configuration.runtime_flags,
                state_aggregator=self._context.services.infrastructure.state_aggregator,
                terminal=self._context.services.infrastructure.hardware.terminal,
            )
        )
        self._power_operation_supervisor = PowerOperationSupervisor(
            PowerOperationSupervisorDependencies(
                repository=self._context.services.databases.power_operations,
                dispatcher=power_dispatcher,
                event_publisher=PowerOperationEventPublisher(
                    PowerOperationEventPublisherDependencies(
                        event_bus=self._context.services.infrastructure.event_bus,
                        logger=get_logger(LOGGER_NAME),
                    )
                ),
                cancellation_binder=self._context.services.tasks.cancellation.binder,
                finalizer_tracker=self._context.services.tasks.cancellation.finalizer_tracker,
                logger=get_logger(LOGGER_NAME),
            )
        )
        self._host_instance = ApplicationHostInstance(
            metadata=assembly.metadata,
            paths=self._context.paths,
            runtime=self._context.runtime,
            security=assembly.security,
            services=self._context.services,
            api_runtime_singletons=assembly.api_runtime_singletons,
            application_control=self._application_control,
            power_operation_supervisor=self._power_operation_supervisor,
            edition_composition=assembly.edition_composition,
        )
        self._context.services.databases.core.writer.bind_lineage_escalation(
            self._escalate_wal_lineage_fault,
        )

    def _escalate_wal_lineage_fault(self, reason: str) -> None:
        self._context.logging.lifecycle_logger.critical(
            "Database WAL lineage violation reported by the writer: %s. Restarting the application to reopen a single healthy database lineage.",
            reason,
        )
        self._application_control.restart()

    @property
    def context(self) -> ApplicationContext:
        return self._context

    async def start(self) -> None:
        await self._controller_services.preflight.run(
            self._controller_services.recovery.handle_system_restart_requested_event,
        )
        if not await self._controller_services.startup.start_before_host(self.context):
            return
        await self._power_operation_supervisor.start()
        await self._controller_services.host.start(self._host_instance)
        await self._controller_services.startup.finalize_after_host(self.context)

    async def shutdown(self) -> None:
        await self._power_operation_supervisor.shutdown()
        await self._controller_services.shutdown.shutdown(self.context)

    def restart(self) -> None:
        self._application_control.restart()

    async def update(self) -> tuple[ApplicationUpdateOutcome, str]:
        return await self._application_control.update()

    async def _update_plugin_worker_runtime_flags(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
    ) -> None:
        plugin_manager = self._context.services.plugins.plugin_manager
        await plugin_manager.update_runtime_flags(runtime_flags)
