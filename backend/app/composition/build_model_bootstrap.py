"""SoAI - Model bootstrap composition for application assembly [backend/app/composition/build_model_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.composition.model_services_cache_and_state import build_model_record_locks
from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.models.protocols_database import DatabaseModelsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from models.actions.purge_records import (
    ModelDatabasePurgeService,
    ModelDatabasePurgeServiceDependencies,
)
from models.manager.registry import ModelRegistry, ModelRegistryDependencies
from models.parameters.manager import ParameterManager, ParameterManagerDependencies
from models.providers.coordinator import (
    ModelProviderCoordinator,
    ModelProviderCoordinatorDependencies,
)

__all__ = ("build_model_bootstrap_components",)

LOGGER_NAME = "SoAI.app.composition.build_model_bootstrap"


def build_model_bootstrap_components(
    *,
    database_models: DatabaseModelsProtocol,
    database_plugins: DatabasePluginsProtocol,
    event_bus: EventBusProtocol,
) -> tuple[
    ParameterManager,
    ModelDatabasePurgeService,
    ModelRegistry,
    ModelProviderCoordinator,
    TTLAsyncLockRegistry[str],
]:
    model_record_locks = build_model_record_locks()
    parameter_manager_instance = ParameterManager(
        ParameterManagerDependencies(logger=get_logger(LOGGER_NAME)),
    )
    model_database_purge_service = ModelDatabasePurgeService(
        ModelDatabasePurgeServiceDependencies(
            database_models=database_models,
            event_bus=event_bus,
            model_record_locks=model_record_locks,
        ),
    )
    model_registry = ModelRegistry(
        ModelRegistryDependencies(
            database_models=database_models,
            database_plugins=database_plugins,
        ),
    )
    model_provider_coordinator = ModelProviderCoordinator(
        ModelProviderCoordinatorDependencies(
            database=database_plugins,
        ),
    )
    return (
        parameter_manager_instance,
        model_database_purge_service,
        model_registry,
        model_provider_coordinator,
        model_record_locks,
    )
