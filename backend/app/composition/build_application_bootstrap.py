"""SoAI - Bootstrap phase composition for application assembly [backend/app/composition/build_application_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx2

from app.application_dependencies import ApplicationEnvironment, ApplicationModuleDependencies
from app.backup.restore_startup_recovery import recover_interrupted_restore
from app.composition.application_bootstrap_database_and_tasks import (
    build_database_config_manager_tasks_and_http_client,
)
from app.composition.application_bootstrap_hardware_metrics import (
    build_hardware_and_metrics_services,
)
from app.composition.application_bootstrap_state import ApplicationBootstrapState
from app.composition.application_bootstrap_state_assembly import (
    assemble_bootstrap_state_and_finalize,
)
from app.composition.bootstrap_failure_cleanup import cleanup_failed_bootstrap
from app.composition.build_application_bootstrap_core import (
    CoreBootstrapStage,
    build_core_bootstrap_stage,
)
from app.composition.build_core_configuration import (
    configure_webui_defaults,
)
from app.composition.build_paths import build_application_paths
from app.composition.build_security import build_security_services
from app.composition.build_tasks import TaskRegistryFactoryResult
from app.config.service import ConfigManager
from app.edition_composition import EditionComposition
from app.types_services_database import DatabaseServices
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("build_application_bootstrap",)


async def build_application_bootstrap(
    *,
    environment: ApplicationEnvironment,
    module_dependencies: ApplicationModuleDependencies,
    stop_event: asyncio.Event,
    application_logger: LoggerProtocol,
    bootstrap_logger: LoggerProtocol,
    lifecycle_logger: LoggerProtocol,
    gui_status: Callable[[str], None],
    edition_composition: EditionComposition,
) -> ApplicationBootstrapState:
    core_stage: CoreBootstrapStage | None = None
    database_services: DatabaseServices | None = None
    config_manager: ConfigManager | None = None
    task_registry_result: TaskRegistryFactoryResult | None = None
    http_client: httpx2.AsyncClient | None = None
    try:
        await recover_interrupted_restore(
            project_root=environment.base_dir,
            log=application_logger,
        )
        core_stage = await build_core_bootstrap_stage(
            environment=environment,
            module_dependencies=module_dependencies,
            stop_event=stop_event,
            application_logger=application_logger,
            bootstrap_logger=bootstrap_logger,
            lifecycle_logger=lifecycle_logger,
            gui_status=gui_status,
            edition_composition=edition_composition,
        )
        runtime_foundation = core_stage.runtime_foundation
        runtime_state = runtime_foundation.runtime_state
        cancellation_system = runtime_foundation.cancellation_system
        configuration_foundation = core_stage.configuration_foundation
        config = configuration_foundation.config
        files = configuration_foundation.files
        runtime_flags_service = configuration_foundation.runtime_flags_service
        configuration_data = configuration_foundation.configuration_data
        event_bus = core_stage.event_bus
        logging_instance = core_stage.logging_instance
        disk_speed_test_service = core_stage.disk_speed_test_service
        network_speed_test_service = core_stage.network_speed_test_service
        paths = build_application_paths(
            environment=environment,
            config=config,
            files=files,
        )
        security = build_security_services(config=config)
        configure_webui_defaults(
            config=config,
            files=files,
            runtime_state=runtime_state,
            logging_instance=logging_instance,
            base_dir=environment.base_dir,
            edition=edition_composition.capabilities.edition,
            webui_relative_path=edition_composition.capabilities.webui_relative_path,
            webui_fallback_relative_paths=edition_composition.capabilities.webui_fallback_relative_paths,
        )
        (
            database_services,
            config_manager,
            routing_config,
            task_registry_result,
            http_client,
        ) = await build_database_config_manager_tasks_and_http_client(
            environment=environment,
            runtime_foundation=runtime_foundation,
            cancellation_system=cancellation_system,
            config=config,
            files=files,
            configuration_data=configuration_data,
            runtime_flags_service=runtime_flags_service,
            event_bus=event_bus,
            application_logger=application_logger,
            paths=paths,
            encryption_key_tuple=security.fernet,
            mutation_storage=edition_composition.durable_mutations.storage,
            task_catalog=edition_composition.tasks.catalog,
        )
        hardware_services = build_hardware_and_metrics_services(
            environment=environment,
            runtime_state=runtime_state,
            config=config,
            files=files,
            runtime_flags_service=runtime_flags_service,
            event_bus=event_bus,
            database_services=database_services,
            cancellation_system=cancellation_system,
            runtime_foundation=runtime_foundation,
            disk_speed_test_service=disk_speed_test_service,
            network_speed_test_service=network_speed_test_service,
        )
        return assemble_bootstrap_state_and_finalize(
            core_stage=core_stage,
            paths=paths,
            security=security,
            database_services=database_services,
            config_manager=config_manager,
            routing_config=routing_config,
            task_registry_result=task_registry_result,
            http_client=http_client,
            hardware_manager=hardware_services.hardware_manager,
            hardware_gpu_tuning=hardware_services.hardware_gpu_tuning,
            hardware_activity_registry=hardware_services.hardware_activity_registry,
            terminal=hardware_services.terminal,
            storage_manager=hardware_services.storage_manager,
            prompt_token_counter=hardware_services.prompt_token_counter,
            command_executor=hardware_services.command_executor,
            metrics_manager=hardware_services.metrics_manager,
            state_aggregator=hardware_services.state_aggregator,
            edition_composition=edition_composition,
        )
    except asyncio.CancelledError:
        await cleanup_failed_bootstrap(
            core_stage=core_stage,
            database_services=database_services,
            config_manager=config_manager,
            task_registry_result=task_registry_result,
            http_client=http_client,
            logger=application_logger,
        )
        raise
    except HTTP_RECOVERABLE_EXCEPTIONS:
        await cleanup_failed_bootstrap(
            core_stage=core_stage,
            database_services=database_services,
            config_manager=config_manager,
            task_registry_result=task_registry_result,
            http_client=http_client,
            logger=application_logger,
        )
        raise
