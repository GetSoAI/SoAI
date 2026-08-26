"""SoAI - Model service lifecycle coordination and discovery management [backend/models/manager/coordinator/model_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exceptions import StateError
from core.events.subscriptions import subscribe_many, unsubscribe_many
from core.events.types_base import Event
from core.events.types_models_model_commands import (
    DeleteModelAliasCommand,
    DeleteModelParametersCommand,
    ModelDeleteCommand,
    ResetModelOpenAICapabilityOverridesCommand,
    TriggerModelDiscoveryCommand,
    UpdateModelAliasCommand,
    UpdateModelEnabledCommand,
    UpdateModelOpenAICapabilityOverrideCommand,
    UpdateModelParametersCommand,
)
from core.events.types_models_model_events import (
    ModelDatabaseChangeEvent,
    ModelParametersRequireReloadEvent,
)
from core.events.types_models_routing_events import RoutingConfigChangedEvent
from core.events.types_plugins import (
    CircuitBreakerStateChangedEvent,
    InstalledPluginsChangedEvent,
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
    ProviderDiscoveryRequestedEvent,
    ProviderStatusUpdatedEvent,
    PurgeModelsForPluginCommand,
)
from core.events.types_system import (
    ConfigAppliedEvent,
    SystemRestartRequiredEvent,
)
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.protocols import Shutdownable
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.runtime.startup_status import StartupPhaseResult
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.service_lifecycle import ServiceLifecycle, ServiceLifecycleDependencies
from models.manager.coordinator.dependencies import ModelManagerDependencies
from models.manager.coordinator.event_handlers import ModelManagerEventHandlers
from models.manager.coordinator.plugin_event_handlers import (
    ModelManagerPluginEventHandlers,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ModelManager",
    "create_linked_task",
)

LOGGER_NAME = "SoAI.models.manager.model_manager"


def create_linked_task(
    coro: Awaitable[None],
    *,
    name: str,
    cancellation_id: str,
    owner: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: LoggerProtocol,
    metadata: dict[str, JSONValue] | None = None,
) -> asyncio.Task[None]:
    return spawn_tracked_task(
        coro,
        name=name,
        cancellation_id=cancellation_id,
        owner=owner,
        metadata=metadata,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


class ModelManager(Shutdownable):

    def __init__(self, deps: ModelManagerDependencies) -> None:
        logger = get_logger(LOGGER_NAME)
        self._deps = deps
        self._lifecycle = ServiceLifecycle(
            ServiceLifecycleDependencies(
                cancellation_binder=deps.cancellation_binder,
                finalizer_tracker=deps.finalizer_tracker,
                managed_task_group_label="model services coordinator",
                managed_task_group_logger=logger,
            ),
        )
        self.shutdown_event = deps.shutdown_event
        self.cancellation_binder = self._lifecycle.cancellation_binder
        self.finalizer_tracker = self._lifecycle.finalizer_tracker
        background_tasks = self._lifecycle.managed_task_group
        if background_tasks is None:
            raise StateError("Coordinator lifecycle did not initialize a managed task group.")
        self._background_tasks: ManagedTaskGroup = background_tasks
        self._command_handlers = ModelManagerEventHandlers(
            deps=deps,
            background_tasks=self._background_tasks,
            shutdown_event=self.shutdown_event,
        )
        self._plugin_handlers = ModelManagerPluginEventHandlers(
            deps=deps,
            shutdown_event=self.shutdown_event,
        )
        self._event_subscriptions: dict[type[Event], Callable[[Event], Awaitable[None]]] = {}
        self._cache_subscriptions: dict[type[Event], Callable[[Event], Awaitable[None]]] = {}
        self._durable_subscriptions: dict[type[Event], Callable[[Event], Awaitable[None]]] = {}
        self._subscriptions_registered = False
        self.model_services_ready_event = self._deps.model_services_ready_event
        self.startup_discovery_complete_event = (
            self._deps.model_discovery_service.startup_discovery_complete_event
        )

    @property
    def startup_discovery_result(self) -> StartupPhaseResult:
        return self._deps.model_discovery_service.startup_discovery_result

    async def initialize(self) -> None:
        logger = get_logger(LOGGER_NAME)
        self.shutdown_event.clear()
        self._subscribe_events()
        await self._plugin_handlers.seed_installed_plugin_names_snapshot()
        await self._deps.model_parameter_mutations.start()
        startup_task = create_linked_task(
            self._deps.model_discovery_service.model_run_startup_discovery(),
            name="model-coordinator-startup-discovery",
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "model_coordinator",
                    "startup_discovery",
                    safe_or_hashed_segment(str(id(self))),
                ),
            ),
            owner="model_startup_discovery",
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            logger=logger,
            metadata={"plugin_count": len(self._deps.installed_plugin_names_ref())},
        )
        _ = self._background_tasks.track(startup_task)
        refresh_interval_ms = self._deps.config.get_int(
            "MODELS.MANAGER.PERFORMANCE.BACKGROUND_REFRESH_INTERVAL_MS",
        )
        refresh_task = create_linked_task(
            self._deps.model_discovery_service.model_background_refresh_loop(refresh_interval_ms),
            name="model-coordinator-background-refresh",
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "model_coordinator",
                    "refresh_loop",
                    safe_or_hashed_segment(str(id(self))),
                ),
            ),
            owner="model_refresh_loop",
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            logger=logger,
            metadata={"interval_ms": int(max(1, int(refresh_interval_ms)))},
        )
        _ = self._background_tasks.track(refresh_task)
        self.model_services_ready_event.set()

    async def _handle_model_list_cache_invalidation_event(self, event: Event) -> None:
        if self.shutdown_event.is_set():
            return
        if not isinstance(
            event,
            ModelDatabaseChangeEvent
            | RoutingConfigChangedEvent
            | CircuitBreakerStateChangedEvent
            | PluginInstallationStateChangedEvent
            | PluginRuntimeStateChangedEvent
            | ProviderStatusUpdatedEvent
            | SystemRestartRequiredEvent,
        ):
            return
        if isinstance(event, ModelDatabaseChangeEvent) and (
            event.added_universal_ids or event.removed_universal_ids
        ):
            for universal_id in event.removed_universal_ids:
                await self._deps.model_parameter_cache.invalidate(universal_id)
            await self._deps.model_resolution_service.model_invalidate_resolution_cache()
        if isinstance(event, ProviderStatusUpdatedEvent):
            await self._deps.model_resolution_service.model_invalidate_resolution_cache()
        await self._deps.model_information_service.model_invalidate_list_caches()

    def _subscribe_events(self) -> None:
        if self._subscriptions_registered:
            return
        self._event_subscriptions = {
            ModelDeleteCommand: self._command_handlers.handle_delete_model_command,
            PurgeModelsForPluginCommand: self._command_handlers.handle_purge_models_for_plugin_command,
            TriggerModelDiscoveryCommand: self._command_handlers.handle_discover_models_command,
            InstalledPluginsChangedEvent: self._plugin_handlers.handle_installed_plugins_changed,
            UpdateModelParametersCommand: self._command_handlers.handle_parameter_command,
            DeleteModelParametersCommand: self._command_handlers.handle_parameter_command,
            UpdateModelAliasCommand: self._command_handlers.handle_alias_command,
            DeleteModelAliasCommand: self._command_handlers.handle_alias_command,
            UpdateModelEnabledCommand: self._command_handlers.handle_enabled_command,
            UpdateModelOpenAICapabilityOverrideCommand: (
                self._command_handlers.handle_openai_capabilities_override_command
            ),
            ResetModelOpenAICapabilityOverridesCommand: (
                self._command_handlers.handle_openai_capabilities_override_command
            ),
            PluginInstallationStateChangedEvent: (
                self._plugin_handlers.handle_plugin_install_state_change
            ),
            PluginRuntimeStateChangedEvent: self._plugin_handlers.handle_plugin_enabled_status_change,
            ConfigAppliedEvent: self._plugin_handlers.handle_plugin_config_applied,
            ModelParametersRequireReloadEvent: self._command_handlers.handle_parameters_require_reload,
        }
        self._cache_subscriptions = dict.fromkeys(
            (
                ModelDatabaseChangeEvent,
                RoutingConfigChangedEvent,
                CircuitBreakerStateChangedEvent,
                PluginInstallationStateChangedEvent,
                PluginRuntimeStateChangedEvent,
                ProviderStatusUpdatedEvent,
                SystemRestartRequiredEvent,
            ),
            self._handle_model_list_cache_invalidation_event,
        )
        self._durable_subscriptions = {
            ProviderDiscoveryRequestedEvent: (
                self._plugin_handlers.handle_provider_discovery_requested
            ),
        }
        subscribe_many(self._deps.event_bus, self._event_subscriptions)
        subscribe_many(self._deps.event_bus, self._cache_subscriptions)
        subscribe_many(self._deps.domain_event_delivery, self._durable_subscriptions)
        self._subscriptions_registered = True

    def _unsubscribe_events(self) -> None:
        if not self._subscriptions_registered:
            return
        unsubscribe_many(self._deps.event_bus, self._event_subscriptions)
        unsubscribe_many(self._deps.event_bus, self._cache_subscriptions)
        unsubscribe_many(self._deps.domain_event_delivery, self._durable_subscriptions)
        self._event_subscriptions = {}
        self._cache_subscriptions = {}
        self._durable_subscriptions = {}
        self._subscriptions_registered = False

    @override
    async def shutdown(self) -> None:
        self.shutdown_event.set()
        self._unsubscribe_events()
        await self._deps.model_parameter_mutations.shutdown()
        await self._background_tasks.cancel()
