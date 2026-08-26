"""SoAI - Model subsystem composition for application assembly [backend/app/composition/build_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.composition.model_services_cache_and_state import (
    InstalledPluginNamesState,
    build_model_service_caches,
)
from app.composition.model_services_core_dependencies import (
    ModelServicesCoreDependencies,
)
from app.composition.model_services_information_virtual import (
    build_model_information_and_virtual_coordinator,
)
from app.composition.model_services_stack import build_model_stack_and_manager
from app.types_services_runtime import ModelServices
from core.logging.trace import get_logger
from core.models.protocols import ModelProviderCoordinatorProtocol
from core.tasks.service_lifecycle import ServiceLifecycle, ServiceLifecycleDependencies

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = ("build_model_services",)

LOGGER_NAME = "SoAI.app.composition.build_models"


def _coerce_model_service_cache_config(
    raw: ConfigValue,
) -> dict[str, int | float | str | bool | None]:
    if not isinstance(raw, dict):
        return {}
    coerced: dict[str, int | float | str | bool | None] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            continue
        if value is None or isinstance(value, int | float | str | bool):
            coerced[key] = value
    return coerced


def build_model_services(
    *,
    core_deps: ModelServicesCoreDependencies,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
) -> ModelServices:
    model_manager_config_raw = core_deps.config.get("MODELS.MANAGER", {})
    model_manager_config = (
        model_manager_config_raw if isinstance(model_manager_config_raw, dict) else {}
    )
    ms_cache_raw = model_manager_config.get("CACHE", {})
    ms_cache_config = _coerce_model_service_cache_config(ms_cache_raw)
    model_services_ready_event = asyncio.Event()
    installed_plugin_names_state = InstalledPluginNamesState()
    installed_plugin_names_ref = installed_plugin_names_state.ref
    set_installed_plugin_names = installed_plugin_names_state.set_names
    (
        resolution_cache_lock,
        resolution_cache,
        parameter_cache,
    ) = build_model_service_caches(ms_cache_config)
    model_record_locks = core_deps.model_record_locks
    model_information_service, virtual_model_coordinator = (
        build_model_information_and_virtual_coordinator(
            database_models=core_deps.database_models,
            database_plugins=core_deps.database_plugins,
            plugin_manager=core_deps.plugin_manager,
            state_aggregator=core_deps.state_aggregator,
            model_registry=core_deps.model_registry,
            parameter_manager=core_deps.parameter_manager,
            installed_plugin_names_ref=installed_plugin_names_ref,
            event_bus=core_deps.event_bus,
            routing_config_holder=core_deps.routing_config_holder,
            resolution_cache_lock=resolution_cache_lock,
            resolution_cache=resolution_cache,
        )
    )
    model_services_lifecycle = ServiceLifecycle(
        ServiceLifecycleDependencies(
            cancellation_binder=core_deps.cancellation_binder,
            finalizer_tracker=core_deps.finalizer_tracker,
            managed_task_group_label="model services background tasks",
            managed_task_group_logger=get_logger(LOGGER_NAME),
        ),
    )
    model_services_shutdown_event = model_services_lifecycle.shutdown_event
    (
        model_manager,
        model_resolution_service,
        model_parameter_service,
        model_virtual_model_service,
    ) = build_model_stack_and_manager(
        core_deps=core_deps,
        installed_plugin_names_ref=installed_plugin_names_ref,
        set_installed_plugin_names=set_installed_plugin_names,
        model_services_ready_event=model_services_ready_event,
        model_services_shutdown_event=model_services_shutdown_event,
        resolution_cache_lock=resolution_cache_lock,
        resolution_cache=resolution_cache,
        parameter_cache=parameter_cache,
        model_record_locks=model_record_locks,
        model_information_service=model_information_service,
        virtual_model_coordinator=virtual_model_coordinator,
    )
    return ModelServices(
        model_coordinator=model_manager,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_parameter_service=model_parameter_service,
        model_virtual_model_service=model_virtual_model_service,
        model_provider_coordinator=model_provider_coordinator,
    )
