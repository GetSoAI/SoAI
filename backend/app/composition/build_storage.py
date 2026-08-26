"""SoAI - Storage service composition for application assembly [backend/app/composition/build_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from app.backup.backup_service import ApplicationBackupService
from app.backup.service_dependencies import ApplicationBackupServiceDependencies
from app.composition.storage_file_explorer_composition import (
    build_file_explorer_services,
)
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.lifecycle.signals import require_runtime_restart
from app.media_parsing_services import MediaParsingServices
from app.types_services_runtime import StorageServices
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
from core.files.protocols import DatabaseFilesProtocol
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.hardware.protocols_storage import StorageManagerProtocol
from core.licensing.types import Edition
from core.logging.trace import get_logger
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from files.dependencies import FileManagerDependencies
from files.manager import FileManager
from files.settings import resolve_file_manager_settings

__all__ = ("build_storage_services",)

BACKUP_RESTORE_LOGGER_NAME = "SoAI.app.backup.restore"


def build_storage_services(
    *,
    edition: Edition,
    config: ConfigProtocol,
    files: FilesProtocol,
    runtime_state: RuntimeStateStoreProtocol,
    event_bus: EventBusProtocol,
    domain_event_delivery: DurableEventDeliveryProtocol,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task_registry: TaskRegistryProtocol,
    database_core: DatabaseCoreProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    database_files: DatabaseFilesProtocol,
    orchestrator_control: OrchestratorControlProtocol,
    config_manager: ConfigManagerProtocol,
    storage_manager: StorageManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    media_parsing: MediaParsingServices,
) -> StorageServices:
    _ = domain_event_delivery
    storage_root = resolve_managed_files_storage_root(config, files)
    perform_startup_cleanup, reconciliation_concurrency, directory_scan_timeout = (
        resolve_file_manager_settings(config)
    )
    file_manager = FileManager(
        FileManagerDependencies(
            config=config,
            database_files=database_files,
            storage_manager=storage_manager,
            event_bus=event_bus,
            shutdown_event=runtime_state.shutdown_event,
            storage_root=storage_root,
            perform_startup_cleanup=perform_startup_cleanup,
            reconciliation_concurrency=reconciliation_concurrency,
            directory_scan_timeout_seconds=directory_scan_timeout,
            cancellation_coordinator=cancellation_coordinator,
            cancellation_history=cancellation_history,
            cancellation_event_bus=cancellation_event_bus,
            token_collection=token_collection,
            cancellation_binder=cancellation_binder,
            task_registry=task_registry,
        ),
    )
    lifecycle_coordinator.register_actor(file_manager)
    backup_service = ApplicationBackupService(
        ApplicationBackupServiceDependencies(
            edition=edition,
            config=config,
            files=files,
            event_bus=event_bus,
            task_registry=task_registry,
            task_cancellation_binder=cancellation_binder,
            task_finalizer_tracker=finalizer_tracker,
            cancellation_coordinator=cancellation_coordinator,
            database_core=database_core,
            database_notifications=database_notifications,
            orchestrator_control=orchestrator_control,
            config_manager=config_manager,
            storage_manager=storage_manager,
            request_restart=partial(
                require_runtime_restart,
                runtime_state,
                get_logger(BACKUP_RESTORE_LOGGER_NAME),
            ),
            startup_ready_event=runtime_state.startup_ready_event,
        ),
    )
    lifecycle_coordinator.register_actor(backup_service)
    file_explorer_enabled = config.get_bool("DATA.FILE_EXPLORER.ENABLED")
    file_explorer_core = None
    file_explorer_batch = None
    file_explorer_tasks = None
    file_explorer_search = None
    file_explorer_download = None
    file_explorer_listings = None
    if file_explorer_enabled:
        explorer = build_file_explorer_services(
            config=config,
            files=files,
            event_bus=event_bus,
            task_registry=task_registry,
            cancellation_binder=cancellation_binder,
            storage_manager=storage_manager,
            lifecycle_coordinator=lifecycle_coordinator,
        )
        file_explorer_core = explorer.core
        file_explorer_batch = explorer.batch
        file_explorer_tasks = explorer.tasks
        file_explorer_search = explorer.search
        file_explorer_download = explorer.download
        file_explorer_listings = explorer.listings

    return StorageServices(
        file_manager=file_manager,
        backup_service=backup_service,
        document_reader=media_parsing.document_reader,
        parser_registry_factory=media_parsing.parser_registry_factory,
        media_parsing=media_parsing,
        file_explorer_core=file_explorer_core,
        file_explorer_batch=file_explorer_batch,
        file_explorer_tasks=file_explorer_tasks,
        file_explorer_search=file_explorer_search,
        file_explorer_download=file_explorer_download,
        file_explorer_listings=file_explorer_listings,
    )
