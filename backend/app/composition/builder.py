"""SoAI - Application service and dependency assembly [backend/app/composition/builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.builder_dependencies import ApplicationAssemblyBuilderDependencies
from app.composition.build_api_runtime_singletons import build_api_runtime_singletons
from app.composition.build_application_bootstrap import build_application_bootstrap
from app.composition.build_application_services import build_application_services
from app.composition.build_licensing import build_licensing_services
from app.composition.service_composition_failure_cleanup import (
    cleanup_failed_service_composition,
)
from app.types_application import ApplicationAssembly
from app.types_services import ApplicationServices
from app.types_services_licensing import LicensingServices
from app.types_services_runtime import LifecycleServices
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms

__all__ = ("ApplicationAssemblyBuilder",)

LOGGER_NAME = "SoAI.app.composition.builder"


class ApplicationAssemblyBuilder:
    def __init__(self, deps: ApplicationAssemblyBuilderDependencies) -> None:
        self.environment = deps.environment
        self.stop_event = deps.stop_event
        self.gui_status = deps.gui_status
        self.bootstrap_logger = deps.bootstrap_logger
        self.lifecycle_logger = deps.lifecycle_logger
        self.startup_timings = deps.startup_timings
        self.module_dependencies = deps.module_dependencies
        self.edition_composition = deps.edition_composition
        self.application_logger = get_logger(LOGGER_NAME)

    async def build(self) -> ApplicationAssembly:
        bootstrap_started_ms = monotonic_ms()
        bootstrap_state = await build_application_bootstrap(
            environment=self.environment,
            module_dependencies=self.module_dependencies,
            stop_event=self.stop_event,
            application_logger=self.application_logger,
            bootstrap_logger=self.bootstrap_logger,
            lifecycle_logger=self.lifecycle_logger,
            gui_status=self.gui_status,
            edition_composition=self.edition_composition,
        )
        self.startup_timings.record_since_ms(
            "assembly.build_application_bootstrap_ms",
            bootstrap_started_ms,
        )
        api_runtime_singletons = None
        licensing_services: LicensingServices | None = None
        application_assembly: ApplicationAssembly | None = None
        services_started_ms = monotonic_ms()
        try:
            api_runtime_singletons = build_api_runtime_singletons(
                cancellation_binder=bootstrap_state.task_services.task_cancellation_binder,
                finalizer_tracker=bootstrap_state.task_services.task_finalizer_tracker,
                config=bootstrap_state.configuration_services.config,
                event_bus=bootstrap_state.event_bus,
            )
            restart_requester = (
                bootstrap_state.runtime_foundation.runtime_state.system_restart_requester
            )
            if restart_requester is None:
                raise StateError("System restart requester is unavailable during composition.")
            licensing_services = await build_licensing_services(
                project_root=bootstrap_state.paths.base_dir,
                policy=self.edition_composition.licensing,
                repository=bootstrap_state.database_services.licensing,
                wizard_repository=bootstrap_state.database_services.licensing_wizard,
                database_plugins=bootstrap_state.database_services.plugins,
                runtime_flags=bootstrap_state.configuration_services.runtime_flags,
                cancellation_binder=(bootstrap_state.task_services.task_cancellation_binder),
                finalizer_tracker=bootstrap_state.task_services.task_finalizer_tracker,
                database_users=bootstrap_state.database_services.users,
                runtime_state=bootstrap_state.runtime_foundation.runtime_state,
                restart_requester=restart_requester,
            )
            service_composition = await build_application_services(
                bootstrap_state=bootstrap_state,
                updater_module_dependencies=self.module_dependencies.updater,
                lifecycle_logger=self.lifecycle_logger,
                startup_timings=self.startup_timings,
                edition_composition=self.edition_composition,
                licensing_status=licensing_services.runtime,
            )
            self.startup_timings.record_since_ms(
                "assembly.build_application_services_ms",
                services_started_ms,
            )
            bootstrap_state.runtime_foundation.lifecycle_coordinator.register_actor(
                licensing_services.recovery_actor
            )
            application_assembly = ApplicationAssembly(
                environment=self.environment,
                metadata=bootstrap_state.runtime_foundation.metadata,
                paths=bootstrap_state.paths,
                logging=bootstrap_state.logging_instance,
                security=bootstrap_state.security,
                runtime=bootstrap_state.runtime_foundation.runtime_state,
                api_runtime_singletons=api_runtime_singletons,
                services=ApplicationServices(
                    configuration=bootstrap_state.configuration_services,
                    infrastructure=service_composition.infrastructure_services,
                    licensing=licensing_services,
                    databases=bootstrap_state.database_services,
                    tasks=bootstrap_state.task_services,
                    orchestrator=service_composition.orchestrator_services,
                    plugins=service_composition.plugin_services,
                    storage=service_composition.storage_services,
                    model_context_protocol=service_composition.model_context_protocol_services,
                    lifecycle=LifecycleServices(
                        coordinator=bootstrap_state.runtime_foundation.lifecycle_coordinator,
                        discovery_service=bootstrap_state.runtime_foundation.discovery_service,
                    ),
                    models=service_composition.model_services,
                    host_management=service_composition.host_management_services,
                ),
                module_dependencies=self.module_dependencies,
                edition_composition=self.edition_composition,
            )
        finally:
            if application_assembly is None:
                if licensing_services is not None:
                    await licensing_services.authority_http_client.aclose()
                await cleanup_failed_service_composition(
                    bootstrap_state=bootstrap_state,
                    logger=self.application_logger,
                    login_password_pool=(
                        None
                        if api_runtime_singletons is None
                        else api_runtime_singletons.login_password_pool
                    ),
                )
        if application_assembly is None:
            raise StateError("Application assembly construction completed without a result.")
        return application_assembly
