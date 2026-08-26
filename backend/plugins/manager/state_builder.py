"""SoAI - Plugin manager state construction [backend/plugins/manager/state_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.logging.trace import TraceLogger
from core.meta.versioning import get_core_version
from core.plugins.protocols_manager_dependencies import PluginManagerPathsProtocol
from core.runtime.startup_status import StartupPhaseResult, StartupPhaseStatus
from plugins.alias_hydrator import PluginAliasHydrator, PluginAliasHydratorDependencies
from plugins.manager.dependencies import PluginManagerDependencies
from plugins.manager.state_models import (
    PluginManagerCatalogState,
    PluginManagerConfigurationState,
    PluginManagerDownloadState,
    PluginManagerLifecycleState,
    PluginManagerLockState,
    PluginManagerState,
    PluginManagerValidationState,
)
from plugins.state.transfers import PluginDownloadAgent, PluginDownloadAgentDependencies

__all__ = ("build_plugin_manager_state",)


def _build_plugin_manager_configuration_state(
    deps: PluginManagerDependencies,
) -> PluginManagerConfigurationState:
    uploads_enabled, downloads_enabled, allow_insecure_downloads = deps.transfer_flag_resolver(
        deps.core.config,
    )
    return PluginManagerConfigurationState(
        core_version=get_core_version(),
        uploads_enabled=uploads_enabled,
        downloads_enabled=downloads_enabled,
        allow_insecure_downloads=allow_insecure_downloads,
    )


def build_plugin_manager_state(
    deps: PluginManagerDependencies,
    *,
    paths: PluginManagerPathsProtocol,
    logger: TraceLogger,
) -> PluginManagerState:
    return PluginManagerState(
        lifecycle=PluginManagerLifecycleState(
            alias_hydrator=PluginAliasHydrator(
                PluginAliasHydratorDependencies(
                    database_plugins=deps.databases.plugins,
                    logger=logger,
                ),
            ),
            reconciliation_task=None,
            reconciliation_start_task=None,
            backend_drift_scan_task=None,
            initial_reconciliation_complete=asyncio.Event(),
            initial_reconciliation_result=StartupPhaseResult(StartupPhaseStatus.PENDING),
            initial_reconciliation_error=None,
            fatal_readiness_error=None,
            readiness_degraded_published=False,
            startup_recovery_stop_sweep=set(),
            reconciliation_pending=False,
            reconciliation_pending_lock=asyncio.Lock(),
            reconciliation_start_lock=asyncio.Lock(),
            backend_drift_scan_lock=asyncio.Lock(),
            backend_drift_scan_last_requested_monotonic=0.0,
        ),
        catalog=PluginManagerCatalogState(
            loaded_plugin_surfaces={},
            loaded_plugin_instances={},
            alias_map={},
            known_plugins=set(),
            backend_variant_count_locks=TTLAsyncLockRegistry[str](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=7200.0,
                    max_size=500,
                    cleanup_interval_seconds=600.0,
                ),
            ),
        ),
        validation=PluginManagerValidationState(
            validation_locks=TTLAsyncLockRegistry[str](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=7200.0,
                    max_size=500,
                    cleanup_interval_seconds=600.0,
                ),
            ),
            display_name_cache={},
            display_name_cache_lock=asyncio.Lock(),
        ),
        locks=PluginManagerLockState(
            load_lock=asyncio.Lock(),
        ),
        download=PluginManagerDownloadState(
            download_agent=PluginDownloadAgent(
                PluginDownloadAgentDependencies(
                    temp_directory=paths.temp_directory,
                    logger=logger,
                    cancellation_token_scope=(
                        deps.infrastructure.task_helpers.cancellation_token_scope
                    ),
                ),
            ),
            plugins_with_active_downloads=set(),
            pending_discovery_after_download=set(),
            download_state_lock=asyncio.Lock(),
        ),
        configuration=_build_plugin_manager_configuration_state(deps),
    )
