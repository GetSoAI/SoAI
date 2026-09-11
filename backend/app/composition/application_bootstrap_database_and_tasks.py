"""SoAI - Bootstrap stage database, config manager, tasks, and HTTP client [backend/app/composition/application_bootstrap_database_and_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from app.application_dependencies import ApplicationEnvironment, ApplicationPaths
from app.composition.bootstrap_failure_cleanup import (
    cleanup_database_task_bootstrap_failure,
)
from app.composition.build_cancellation_system import CancellationSystem
from app.composition.build_core_configuration import (
    build_application_routing_config,
    configure_platform_runtime,
    initialize_config_manager,
)
from app.composition.build_core_services import build_http_client
from app.composition.build_database import build_database_services
from app.composition.build_runtime import RuntimeFoundation
from app.composition.build_tasks import (
    TaskRegistryFactoryResult,
    create_task_registry,
    resolve_task_registry_init_values,
)
from app.composition.configuration_json import coerce_configuration_data_json
from app.composition.service_preconditions import require_initialized
from app.composition.startup_reconciliation import (
    reconcile_agent_turns_on_startup,
    reconcile_task_registry,
)
from app.config.dependencies import ConfigManagerDependencies
from app.config.service import ConfigManager
from app.types_services_database import DatabaseServices
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggerProtocol
from core.mutations.storage_composition import MutationStorageComposition
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.flags_service import RuntimeFlagsService
from core.tasks.type_catalog import TaskTypeCatalog

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.config.value_types import ConfigDict

__all__ = ("build_database_config_manager_tasks_and_http_client",)


async def build_database_config_manager_tasks_and_http_client(
    *,
    environment: ApplicationEnvironment,
    runtime_foundation: RuntimeFoundation,
    cancellation_system: CancellationSystem,
    config: ConfigProtocol,
    files: FilesProtocol,
    configuration_data: ConfigDict,
    runtime_flags_service: RuntimeFlagsService,
    event_bus: EventBusProtocol,
    application_logger: LoggerProtocol,
    paths: ApplicationPaths,
    encryption_key_tuple: tuple[Fernet, ...],
    mutation_storage: MutationStorageComposition,
    task_catalog: TaskTypeCatalog,
) -> tuple[
    DatabaseServices,
    ConfigManager,
    RoutingConfig,
    TaskRegistryFactoryResult,
    httpx2.AsyncClient,
]:
    database_services: DatabaseServices | None = None
    config_manager: ConfigManager | None = None
    task_registry_result: TaskRegistryFactoryResult | None = None
    http_client: httpx2.AsyncClient | None = None
    try:
        database_services = await build_database_services(
            config=config,
            files=files,
            encryption_key_tuple=encryption_key_tuple,
            lifecycle_coordinator=runtime_foundation.lifecycle_coordinator,
            event_bus=event_bus,
            cancellation_binder=cancellation_system.binder,
            finalizer_tracker=cancellation_system.finalizer_tracker,
            mutation_storage=mutation_storage,
            task_catalog=task_catalog,
        )
        runtime_foundation.runtime_state.set_database_maintenance(
            database_services.core.vacuum.startup_result
        )
        if database_services.core.vacuum.startup_result.status == "degraded":
            runtime_foundation.runtime_state.set_degraded_mode(True)
        database_tasks = require_initialized(
            database_services.tasks,
            message="Database tasks must be initialized before task registry is built.",
        )
        database_task_queries = require_initialized(
            database_services.task_queries,
            message="Database task queries must be initialized before task registry is built.",
        )
        locks_path = config.get_str("SYSTEM.PATHS.LOCKS")
        if not locks_path:
            raise ValidationError("SYSTEM.PATHS.LOCKS must be configured.")
        locks_directory = files.resolve_path(locks_path)
        config_manager = ConfigManager(
            ConfigManagerDependencies(
                base_path=environment.base_dir,
                core_config_path=environment.config_path,
                config=config,
                event_bus=event_bus,
                cancellation_binder=cancellation_system.binder,
                finalizer_tracker=cancellation_system.finalizer_tracker,
                plugin_directory=paths.plugin_directory,
                lock_directory=locks_directory,
            ),
        )
        runtime_foundation.lifecycle_coordinator.register_actor(config_manager)
        configuration_data_json = coerce_configuration_data_json(configuration_data)
        await initialize_config_manager(
            config_manager=config_manager,
            configuration_data=configuration_data_json,
        )
        await configure_platform_runtime(
            config=config,
            runtime_flags=runtime_flags_service,
        )
        routing_config = build_application_routing_config(
            config=config,
            logger=application_logger,
        )

        task_registry_result = create_task_registry(
            database_tasks,
            database_task_queries,
            event_bus,
            cancellation_system.coordinator,
            cancellation_system.history,
            cancellation_system.binder,
            cancellation_system.finalizer_tracker,
            task_catalog,
            **resolve_task_registry_init_values(config),
        )
        await reconcile_task_registry(
            task_registry=task_registry_result.registry,
            logger=application_logger,
            base_path=environment.base_dir,
        )
        await reconcile_agent_turns_on_startup(
            database_agent_turn_process_boundary=database_services.agent_turn_process_boundary,
            database_agent_turns=database_services.agent_turns,
            database_tool_calls=database_services.tool_calls,
            logger=application_logger,
        )
        http_client = build_http_client(
            config=config,
            runtime_flags=runtime_flags_service,
        )
        return (
            database_services,
            config_manager,
            routing_config,
            task_registry_result,
            http_client,
        )
    except asyncio.CancelledError:
        await cleanup_database_task_bootstrap_failure(
            database_services,
            config_manager,
            task_registry_result,
            http_client,
            application_logger,
        )
        raise
    except HTTP_RECOVERABLE_EXCEPTIONS:
        await cleanup_database_task_bootstrap_failure(
            database_services,
            config_manager,
            task_registry_result,
            http_client,
            application_logger,
        )
        raise
