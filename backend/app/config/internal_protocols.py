"""SoAI - App config internal protocols [backend/app/config/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from ruamel.yaml.comments import CommentedMap

from core.concurrency.task_groups import ManagedTaskGroup
from core.config.protocols import ConfigProtocol
from core.config.types import KnownFileState
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "ConfigCacheProtocol",
    "ConfigCommandHandlersProtocol",
    "ConfigCommandTargetProtocol",
    "ConfigDeleteFromCacheCallable",
    "ConfigIOProtocol",
    "ConfigLoaderProtocol",
    "ConfigManagerLifecycleService",
    "ConfigReconcilerProtocol",
    "ConfigSaveCoordinatorProtocol",
)


class ConfigIOProtocol(Protocol):
    async def read_config_from_disk(self, *, config_name: str) -> CommentedMap | None: ...

    async def read_config_baseline_snapshot_unlocked(
        self,
        *,
        config_path: str,
        config_name: str,
    ) -> tuple[CommentedMap, KnownFileState]: ...

    def get_config_path_sync(self, config_name: str) -> str: ...


class ConfigCacheProtocol(Protocol):
    lock: asyncio.Lock
    configs: dict[str, CommentedMap]

    async def get(self, config_name: str) -> CommentedMap | None: ...

    async def set(self, config_name: str, data: CommentedMap) -> None: ...

    async def delete(self, config_name: str) -> bool: ...

    async def load(
        self,
        config_name: str,
        io_component: ConfigIOProtocol,
        force_reload: bool = False,
    ) -> CommentedMap | None: ...


class ConfigReconcilerProtocol(Protocol):
    reconciliation_lock: asyncio.Lock
    known_files_state: dict[str, KnownFileState]
    file_revisions: dict[str, int]
    initial_baseline_established: bool

    def ensure_revision_initialized(self, path: str) -> int: ...

    def bump_revision(self, path: str) -> int: ...

    async def reconcile_filesystem_state(
        self,
        *,
        update_baseline: bool,
        delete_from_cache: ConfigDeleteFromCacheCallable,
    ) -> None: ...

    async def scan_filesystem_state(
        self,
        *,
        emit_events: bool,
        source: str,
        config_name: str | None,
        delete_from_cache: ConfigDeleteFromCacheCallable,
    ) -> None: ...


class ConfigCommandHandlersProtocol(Protocol):
    async def handle_reconciliation_trigger(self, command: Event) -> None: ...

    async def handle_scan_trigger(self, command: Event) -> None: ...

    async def handle_update_config_command(self, command: Event) -> None: ...


class ConfigManagerLifecycleService(Protocol):
    shutdown_event: asyncio.Event
    subscriptions_registered: bool
    config: ConfigProtocol
    event_bus: EventBusProtocol
    command_handlers: ConfigCommandHandlersProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    logger: LoggerProtocol
    periodic_tasks: ManagedTaskGroup
    reconciler: ConfigReconcilerProtocol

    async def perform_periodic_scan(self) -> None: ...

    async def delete_from_cache(self, config_name: str) -> None: ...


class ConfigDeleteFromCacheCallable(Protocol):
    async def __call__(self, config_name: str) -> None: ...


class ConfigSaveCoordinatorProtocol(Protocol):
    async def save_and_publish(
        self,
        *,
        config_name: str,
        config_path: str,
        data: ConfigValue,
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool: ...


class ConfigLoaderProtocol(Protocol):
    async def load_config(
        self,
        config_name: str,
        force_reload: bool = False,
    ) -> CommentedMap | None: ...


class ConfigCommandTargetProtocol(Protocol):
    logger: LoggerProtocol

    async def establish_baseline(self) -> None: ...

    async def trigger_scan(self, *, config_name: str | None, source: str) -> None: ...

    async def load_config(
        self,
        config_name: str,
        force_reload: bool = False,
    ) -> CommentedMap | None: ...

    async def save_config(
        self,
        config_name: str,
        data: ConfigValue | None = None,
        *,
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool: ...
