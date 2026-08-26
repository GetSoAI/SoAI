"""SoAI - Plugin manager runtime state dataclasses [backend/plugins/manager/state_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import dataclasses

from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.startup_status import StartupPhaseResult
from core.types.json import JSONDict
from plugins.protocols_internal.state.internal_protocols import (
    PluginAliasHydratorProtocol,
    PluginCatalogStateProtocol,
    PluginConfigurationStateProtocol,
    PluginDownloadAgentProtocol,
    PluginDownloadStateProtocol,
    PluginLifecycleStateProtocol,
    PluginLockStateProtocol,
    PluginStateProtocol,
    PluginValidationStateProtocol,
)

__all__ = (
    "PluginManagerCatalogState",
    "PluginManagerConfigurationState",
    "PluginManagerDownloadState",
    "PluginManagerLifecycleState",
    "PluginManagerLockState",
    "PluginManagerState",
    "PluginManagerValidationState",
)


@dataclasses.dataclass(slots=True)
class PluginManagerLifecycleState:
    alias_hydrator: PluginAliasHydratorProtocol
    reconciliation_task: asyncio.Task[None] | None
    reconciliation_start_task: asyncio.Task[None] | None
    backend_drift_scan_task: asyncio.Task[None] | None
    initial_reconciliation_complete: asyncio.Event
    initial_reconciliation_result: StartupPhaseResult
    initial_reconciliation_error: str | None
    fatal_readiness_error: str | None
    readiness_degraded_published: bool
    startup_recovery_stop_sweep: set[str]
    reconciliation_pending: bool
    reconciliation_pending_lock: asyncio.Lock
    reconciliation_start_lock: asyncio.Lock
    backend_drift_scan_lock: asyncio.Lock
    backend_drift_scan_last_requested_monotonic: float


@dataclasses.dataclass(slots=True)
class PluginManagerCatalogState:
    loaded_plugin_surfaces: dict[str, tuple[JSONDict, str]]
    loaded_plugin_instances: dict[str, PluginInstanceProtocol]
    alias_map: dict[str, str]
    known_plugins: set[str]
    backend_variant_count_locks: TTLAsyncLockRegistry[str]


@dataclasses.dataclass(slots=True)
class PluginManagerValidationState:
    validation_locks: TTLAsyncLockRegistry[str]
    display_name_cache: dict[str, str]
    display_name_cache_lock: asyncio.Lock


@dataclasses.dataclass(slots=True)
class PluginManagerLockState:
    load_lock: asyncio.Lock


@dataclasses.dataclass(slots=True)
class PluginManagerDownloadState:
    download_agent: PluginDownloadAgentProtocol
    plugins_with_active_downloads: set[str]
    pending_discovery_after_download: set[str]
    download_state_lock: asyncio.Lock


@dataclasses.dataclass(slots=True)
class PluginManagerConfigurationState:
    core_version: str
    uploads_enabled: bool
    downloads_enabled: bool
    allow_insecure_downloads: bool


@dataclasses.dataclass(slots=True)
class PluginManagerState(PluginStateProtocol):
    lifecycle: PluginLifecycleStateProtocol
    catalog: PluginCatalogStateProtocol
    validation: PluginValidationStateProtocol
    locks: PluginLockStateProtocol
    download: PluginDownloadStateProtocol
    configuration: PluginConfigurationStateProtocol
