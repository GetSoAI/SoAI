"""SoAI - Configuration file manager with change detection [backend/app/config/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, override

from ruamel.yaml.comments import CommentedMap

from app.config.baseline_updates import (
    ConfigBaselineUpdater,
    ConfigBaselineUpdaterDependencies,
)
from app.config.cache import ConfigCache, ConfigCacheDependencies
from app.config.clone import prepare_cloned_config
from app.config.clone_staging import stage_cloned_config
from app.config.dependencies import ConfigManagerDependencies
from app.config.event_handlers import ConfigCommandHandlers
from app.config.internal_protocols import (
    ConfigCommandHandlersProtocol,
    ConfigReconcilerProtocol,
)
from app.config.io import ConfigIO, ConfigIODependencies
from app.config.lifecycle import (
    establish_config_baseline,
    shutdown_config_manager,
    start_config_manager,
    trigger_config_scan,
)
from app.config.paths import (
    get_config_path_sync,
    resolve_base_path,
    resolve_plugins_path,
)
from app.config.reconciler import ConfigReconciler, ConfigReconcilerDependencies
from app.config.saving import ConfigSaveCoordinator, ConfigSaveCoordinatorDependencies
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.task_groups import ManagedTaskGroup
from core.config.locks import get_lock_path
from core.errors.exceptions import StateError, ValidationError
from core.files.locking import async_guarded_file_lock
from core.lifecycle.protocols import Shutdownable
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.service_lifecycle import ServiceLifecycle, ServiceLifecycleDependencies

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("ConfigManager",)

LOGGER_NAME = "SoAI.app.config.service"
PLUGIN_CONFIG_MUTATION_LOCK_NAME = ".plugin-config-mutations"


class ConfigManager(Shutdownable):
    shutdown_event: asyncio.Event
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    periodic_tasks: ManagedTaskGroup
    subscriptions_registered: bool
    logger: LoggerProtocol

    def __init__(self, deps: ConfigManagerDependencies) -> None:
        self._deps = deps
        self.base_path = resolve_base_path(deps.base_path)
        self.plugins_path = resolve_plugins_path(deps.plugin_directory)
        self.config = deps.config
        self.event_bus = deps.event_bus
        self.logger = get_logger(LOGGER_NAME)
        self.lifecycle = ServiceLifecycle(
            ServiceLifecycleDependencies(
                cancellation_binder=deps.cancellation_binder,
                finalizer_tracker=deps.finalizer_tracker,
                managed_task_group_label="config manager periodic tasks",
                managed_task_group_logger=self.logger,
            ),
        )
        self.shutdown_event = self.lifecycle.shutdown_event
        self.cancellation_binder = self.lifecycle.cancellation_binder
        self.finalizer_tracker = self.lifecycle.finalizer_tracker
        periodic_tasks = self.lifecycle.managed_task_group
        if periodic_tasks is None:
            raise StateError("Config manager lifecycle did not initialize a managed task group.")
        self.periodic_tasks = periodic_tasks
        self._cache = ConfigCache(ConfigCacheDependencies(logger=self.logger))
        self.configs = self._cache.configs
        self._creation_locks_registry: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=7200.0,
                max_size=500,
                cleanup_interval_seconds=600.0,
            ),
        )
        self._io = ConfigIO(
            ConfigIODependencies(
                base_path=self.base_path,
                core_config_path=deps.core_config_path,
                plugins_path=self.plugins_path,
                lock_directory=deps.lock_directory,
                logger=self.logger,
            ),
        )
        self.reconciler: ConfigReconcilerProtocol = ConfigReconciler(
            ConfigReconcilerDependencies(
                io=self._io,
                event_bus=self.event_bus,
                logger=self.logger,
                cache=self._cache,
            ),
        )
        self.list_manageable_configs = self.reconciler.list_manageable_configs
        self._saver = ConfigSaveCoordinator(
            ConfigSaveCoordinatorDependencies(
                io=self._io,
                reconciler=self.reconciler,
                cache=self._cache,
                event_bus=self.event_bus,
                logger=self.logger,
            ),
        )
        self.command_handlers: ConfigCommandHandlersProtocol = ConfigCommandHandlers(target=self)
        self._baseline_updater = ConfigBaselineUpdater(
            ConfigBaselineUpdaterDependencies(
                logger=self.logger,
                io_lock_directory=self._io.lock_directory,
                reconciler=self.reconciler,
                io=self._io,
                cache=self._cache,
            ),
        )
        if self.plugins_path:
            self.logger.debug(
                "ConfigManager will look for plugin configs in: %s",
                self.plugins_path,
            )
        self.subscriptions_registered = False

    def creation_lock_for(self, key: str) -> AbstractAsyncContextManager[None]:
        if not key:
            raise ValidationError("Config creation lock key must be provided.")
        return self._creation_locks_registry.lock(key)

    @asynccontextmanager
    async def plugin_config_mutation_scope(
        self,
        config_name: str,
    ) -> AsyncGenerator[None]:
        normalized_name = config_name.strip()
        if not normalized_name:
            raise ValidationError("Plugin config mutation requires a config name.")
        if normalized_name == "core":
            yield
            return
        if not self.plugins_path:
            raise StateError("Plugin directory is not configured.")
        lock_path = get_lock_path(
            os.path.join(self.plugins_path, PLUGIN_CONFIG_MUTATION_LOCK_NAME),
            lock_directory=self._io.lock_directory,
        )
        async with async_guarded_file_lock(
            lock_path,
            timeout=30,
            on_timeout=StateError("Plugin configuration mutation lock acquisition timed out."),
        ):
            yield

    def get_config_path_sync(self, config_name: str) -> str:
        return get_config_path_sync(
            core_config_path=self._deps.core_config_path,
            plugins_path=self.plugins_path,
            config_name=config_name,
        )

    def get_lock_path(self, path: str) -> str:
        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be provided.")
        return get_lock_path(path, lock_directory=self._io.lock_directory)

    async def load_config(
        self,
        config_name: str,
        force_reload: bool = False,
    ) -> CommentedMap | None:
        return await self._cache.load(config_name, self._io, force_reload)

    async def delete_from_cache(self, config_name: str) -> None:
        normalized_config_name = config_name.strip()
        if not normalized_config_name:
            raise ValidationError("config_name is required.")
        await self._cache.delete(normalized_config_name)

    async def save_config(
        self,
        config_name: str,
        data: ConfigValue | None = None,
        *,
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool:
        config_path = self.get_config_path_sync(config_name)
        async with self.plugin_config_mutation_scope(config_name):
            return await self._saver.save_and_publish(
                config_name=config_name,
                config_path=config_path,
                data=data,
                source=source,
                changed_keys=changed_keys,
            )

    async def update_config_transactionally(
        self,
        config_name: str,
        *,
        source: str,
        updater: Callable[[CommentedMap], CommentedMap | dict[str, JSONValue]],
        changed_keys: frozenset[str] | None = None,
    ) -> bool:
        config_path = self.get_config_path_sync(config_name)
        async with self.plugin_config_mutation_scope(config_name):
            return await self._saver.update_and_publish(
                config_name=config_name,
                config_path=config_path,
                updater=updater,
                source=source,
                changed_keys=changed_keys,
            )

    async def build_clone_configuration_snapshot(
        self,
        source_name: str,
        field_overrides: Mapping[str, JSONValue] | None = None,
    ) -> tuple[JSONDict, JSONDict] | None:
        source_config = await self.load_config(source_name, force_reload=True)
        if source_config is None:
            return None
        return prepare_cloned_config(
            source_config,
            field_overrides,
        )

    async def stage_config(
        self,
        config_path: str,
        data: JSONDict,
        reservation: DiskSpaceReservationLeaseProtocol,
        maximum_bytes: int,
    ) -> None:
        await stage_cloned_config(
            config_path,
            data,
            reservation,
            maximum_bytes=maximum_bytes,
        )

    async def rescan_and_update_baseline_for_config(self, config_name: str) -> None:
        config_path = self.get_config_path_sync(config_name)
        await self._baseline_updater.update_baseline_for_config(
            config_name=config_name,
            config_path=config_path,
        )

    def start(self) -> None:
        start_config_manager(self)

    @override
    async def shutdown(self) -> None:
        await shutdown_config_manager(self)

    async def establish_baseline(self) -> None:
        await establish_config_baseline(self)

    async def perform_periodic_scan(self) -> None:
        await self.trigger_scan(config_name=None, source="polling")

    async def trigger_scan(self, *, config_name: str | None, source: str) -> None:
        await trigger_config_scan(self, config_name=config_name, source=source)
