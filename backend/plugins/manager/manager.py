"""SoAI - Central plugin manager service [backend/plugins/manager/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.plugins.logo_contract import PluginLogoResult
from core.plugins.protocols_manager_dependencies import (
    PluginManagerDependenciesProtocol,
    PluginManagerPathsProtocol,
    PluginUpdaterProtocol,
)
from core.runtime.request_context import RequestContext
from core.runtime.startup_status import StartupPhaseResult
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.state.protocols import AuthoritativePluginStateTransitionReceipt
from core.state.state_names import PLUGIN_STATE_NAMES, PluginRuntimeStateName
from core.timing.constants import CONTROL_TIMEOUT_SEC
from plugins.clone.clone_committed_integrity import is_clone_integrity_quarantined
from plugins.identity import require_plugin_identifier
from plugins.logo_preparation import prepare_archive_logo
from plugins.manager.alias_map import is_known_plugin, normalize_plugin_name
from plugins.manager.dependencies import PluginManagerDependencies
from plugins.manager.lifecycle_controller import PluginManagerLifecycleController
from plugins.manager.manager_construction import (
    bind_orchestrator_lifecycle,
    require_plugin_capability,
    require_plugin_manager_online_mode,
    resolve_downloads_enabled,
    resolve_uploads_enabled,
)
from plugins.manager.path_resolver import resolve_plugin_manager_paths
from plugins.manager.public_operations import PluginManagerOperations
from plugins.manager.startup_recovery import perform_startup_backend_stop_sweep
from plugins.manager.state_builder import build_plugin_manager_state
from plugins.path_safety import get_plugin_file_path
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginWorkerControllerProtocol,
)
from plugins.worker.controller import PluginWorkerController

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from plugins.protocols_internal.state.internal_protocols import PluginStateProtocol

__all__ = ("PluginManager",)

LOGGER_NAME = "SoAI.plugins.manager.manager"


class PluginManager(PluginManagerOperations):
    dependencies: PluginManagerDependenciesProtocol
    paths: PluginManagerPathsProtocol
    state: PluginStateProtocol
    updater: PluginUpdaterProtocol
    logger: LoggerProtocol
    orchestrator_lifecycle: OrchestratorLifecycleProtocol | None
    worker_controller: PluginWorkerControllerProtocol

    def __init__(self, deps: PluginManagerDependencies) -> None:
        self.dependencies = deps
        self.lifecycle = deps.infrastructure.lifecycle
        self.task_registry = deps.infrastructure.task_registry
        self.database_plugins = deps.databases.plugins
        self.http_client = deps.core.http_client
        self.state_aggregator = deps.infrastructure.state_aggregator
        self.config_manager = deps.infrastructure.config_manager
        self.event_bus = deps.infrastructure.event_bus
        self.paths = resolve_plugin_manager_paths(deps)
        self.worker_controller = PluginWorkerController(self)
        self.logger = get_logger(LOGGER_NAME)
        self.updater = deps.updater
        self.policy = deps.policy
        self.orchestrator_lifecycle = None
        self.state = build_plugin_manager_state(
            deps,
            paths=self.paths,
            logger=get_logger(LOGGER_NAME),
        )
        self._lifecycle_controller = PluginManagerLifecycleController(self)

    @property
    def lifecycle_controller(self) -> PluginManagerLifecycleController:
        return self._lifecycle_controller

    def bind_orchestrator_lifecycle(
        self,
        orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    ) -> None:
        bind_orchestrator_lifecycle(self, orchestrator_lifecycle)

    def require_online_mode(self, source: str) -> None:
        require_plugin_manager_online_mode(self, source)

    def require_plugin_capability(
        self,
        instance: PluginInstanceProtocol,
        capability_name: str,
        failure_message: str,
    ) -> None:
        require_plugin_capability(self, instance, capability_name, failure_message)

    @property
    def uploads_enabled(self) -> bool:
        return resolve_uploads_enabled(self)

    @property
    def downloads_enabled(self) -> bool:
        return resolve_downloads_enabled(self)

    def normalize_plugin_name(self, plugin_name: str) -> str | None:
        return normalize_plugin_name(self, plugin_name)

    def is_known_plugin(self, plugin_name: str) -> bool:
        return is_known_plugin(self, plugin_name)

    async def is_clone_integrity_quarantined(self, plugin_name: str) -> bool:
        return await is_clone_integrity_quarantined(self, plugin_name)

    async def require_ready(self) -> None:
        await self._lifecycle_controller.require_ready()

    @property
    def initial_reconciliation_result(self) -> StartupPhaseResult:
        return self._lifecycle_controller.initial_reconciliation_result

    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None:
        await self.worker_controller.update_runtime_flags(runtime_flags)

    async def wait_for_initial_reconciliation(self, timeout: float | None = None) -> bool:
        return await self._lifecycle_controller.wait_for_initial_reconciliation(timeout)

    async def mark_reconciliation_pending(self) -> None:
        await self._lifecycle_controller.mark_reconciliation_pending()

    async def run_initial_reconciliation(self) -> None:
        await self._lifecycle_controller.run_initial_reconciliation()

    async def ensure_reconciliation_started(self) -> None:
        await self._lifecycle_controller.ensure_reconciliation_started()

    def start_initial_reconciliation(self) -> None:
        self._lifecycle_controller.start_initial_reconciliation()

    async def initialize(self) -> None:
        await self._lifecycle_controller.initialize()

    async def handle_cancel_task(self, command: Event) -> None:
        await self._lifecycle_controller.handle_cancel_task(command)

    async def shutdown(self) -> None:
        await self._lifecycle_controller.shutdown()

    async def begin_shutdown(self) -> None:
        await self._lifecycle_controller.begin_shutdown()

    async def finalize_shutdown(self) -> None:
        await self._lifecycle_controller.finalize_shutdown()

    async def hydrate_alias_map_from_database(self) -> None:
        await self._lifecycle_controller.hydrate_alias_map_from_database()

    async def perform_startup_recovery_stop_sweep(self) -> None:
        if self.dependencies.infrastructure.lifecycle.disabled:
            return
        self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
        await perform_startup_backend_stop_sweep(self)

    async def transition_plugin_manager_state(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        context: RequestContext | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None:
        lifecycle_publisher = self.dependencies.infrastructure.lifecycle_publisher
        if new_state in PLUGIN_STATE_NAMES:
            return await lifecycle_publisher.begin_installation_transition(
                plugin_name,
                new_state,
                reason,
                context=context,
            )
        return await lifecycle_publisher.begin_runtime_transition(
            plugin_name,
            new_state,
            reason,
            context=context,
        )

    async def prepare_logo(
        self,
        plugin_name: str,
        archive_hash: str,
    ) -> PluginLogoResult | None:
        require_plugin_identifier(plugin_name, invalid_message="Invalid plugin artwork identifier.")
        require_canonical_sha256_hexdigest(archive_hash, label="Plugin archive revision")
        infrastructure = self.dependencies.infrastructure
        database = self.dependencies.databases.plugins
        async with asyncio.timeout(CONTROL_TIMEOUT_SEC):
            async with self.lifecycle.bounded_plugin_lock_scope(
                plugin_name,
                timeout_seconds=CONTROL_TIMEOUT_SEC,
            ) as lock_result:
                if lock_result.acquired:
                    if infrastructure.lifecycle.shutdown_event.is_set():
                        raise StateError("Plugin artwork preparation is unavailable.")
                    records = await database.get_all_listable_plugins(plugin_name)
                    if not records or records[0].get("file_hash") != archive_hash:
                        return None
                    result = await run_bounded_blocking_call(
                        infrastructure.logo_preparation_pool,
                        prepare_archive_logo,
                        plugin_name,
                        get_plugin_file_path(self, plugin_name),
                        archive_hash,
                        infrastructure.logo_cache,
                        total_timeout_sec=CONTROL_TIMEOUT_SEC,
                    )
                    current_records = await database.get_all_listable_plugins(plugin_name)
                    if not current_records or current_records[0].get("file_hash") != archive_hash:
                        return None
                    return result
            raise StateError("Plugin artwork preparation lock timed out.")
