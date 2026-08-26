"""SoAI - Plugin manager state protocols [backend/plugins/protocols_internal/state/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.startup_status import StartupPhaseResult
from core.types.json import JSONDict
from plugins.action_response import PluginActionResponse

if TYPE_CHECKING:
    from core.concurrency.lock_registry import TTLAsyncLockRegistry
    from core.plugins.protocols_manager_dependencies import (
        PluginManagerDependenciesProtocol,
        PluginManagerPathsProtocol,
    )
    from core.runtime.request_context import RequestContext
    from core.types.protocols import HttpClientProtocol

__all__ = (
    "PluginAliasHydratorProtocol",
    "PluginCatalogStateProtocol",
    "PluginConfigurationStateProtocol",
    "PluginDownloadAgentProtocol",
    "PluginDownloadManagerProtocol",
    "PluginDownloadStateProtocol",
    "PluginLifecycleBackendDriftStateProtocol",
    "PluginLifecycleReadinessStateProtocol",
    "PluginLifecycleReconciliationStateProtocol",
    "PluginLifecycleStateProtocol",
    "PluginLockStateProtocol",
    "PluginStateProtocol",
    "PluginValidationStateProtocol",
)


class PluginAliasHydratorProtocol(Protocol):
    async def hydrate(
        self,
        loaded_plugin_surfaces: dict[str, tuple[JSONDict, str]],
    ) -> tuple[dict[str, str] | None, set[str] | None, dict[str, str]]: ...


class PluginDownloadManagerProtocol(Protocol):
    state: PluginStateProtocol
    paths: PluginManagerPathsProtocol

    @property
    def dependencies(self) -> PluginManagerDependenciesProtocol: ...


class PluginDownloadAgentProtocol(Protocol):
    async def download_package(
        self,
        manager: PluginDownloadManagerProtocol,
        url: str,
        context: RequestContext | None,
        http_client: HttpClientProtocol,
    ) -> PluginActionResponse: ...


class PluginLifecycleReconciliationStateProtocol(Protocol):
    reconciliation_task: asyncio.Task[None] | None
    reconciliation_start_task: asyncio.Task[None] | None
    reconciliation_pending: bool
    reconciliation_pending_lock: asyncio.Lock
    reconciliation_start_lock: asyncio.Lock


class PluginLifecycleBackendDriftStateProtocol(Protocol):
    backend_drift_scan_task: asyncio.Task[None] | None
    backend_drift_scan_lock: asyncio.Lock
    backend_drift_scan_last_requested_monotonic: float


class PluginLifecycleReadinessStateProtocol(Protocol):
    initial_reconciliation_complete: asyncio.Event
    initial_reconciliation_result: StartupPhaseResult
    initial_reconciliation_error: str | None
    fatal_readiness_error: str | None
    readiness_degraded_published: bool


class PluginLifecycleStateProtocol(
    PluginLifecycleReconciliationStateProtocol,
    PluginLifecycleBackendDriftStateProtocol,
    PluginLifecycleReadinessStateProtocol,
    Protocol,
):
    alias_hydrator: PluginAliasHydratorProtocol
    startup_recovery_stop_sweep: set[str]


class PluginCatalogStateProtocol(Protocol):
    loaded_plugin_surfaces: dict[str, tuple[JSONDict, str]]
    loaded_plugin_instances: dict[str, PluginInstanceProtocol]
    alias_map: dict[str, str]
    known_plugins: set[str]
    backend_variant_count_locks: TTLAsyncLockRegistry[str]


class PluginValidationStateProtocol(Protocol):
    validation_locks: TTLAsyncLockRegistry[str]
    display_name_cache: dict[str, str]
    display_name_cache_lock: asyncio.Lock


class PluginLockStateProtocol(Protocol):
    load_lock: asyncio.Lock


class PluginDownloadStateProtocol(Protocol):
    download_agent: PluginDownloadAgentProtocol
    plugins_with_active_downloads: set[str]
    pending_discovery_after_download: set[str]
    download_state_lock: asyncio.Lock


class PluginConfigurationStateProtocol(Protocol):
    core_version: str
    uploads_enabled: bool
    downloads_enabled: bool
    allow_insecure_downloads: bool


class PluginStateProtocol(Protocol):
    lifecycle: PluginLifecycleStateProtocol
    catalog: PluginCatalogStateProtocol
    validation: PluginValidationStateProtocol
    locks: PluginLockStateProtocol
    download: PluginDownloadStateProtocol
    configuration: PluginConfigurationStateProtocol
