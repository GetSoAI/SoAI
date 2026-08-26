"""SoAI - Model discovery service scanning plugins for available models [backend/models/discovery/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import VirtualModelConfig
from core.plugins.protocols import PluginManagerProtocol
from core.runtime.startup_status import StartupPhaseResult, StartupPhaseStatus
from core.state.protocols import StateAggregatorProtocol
from core.tasks.periodic import run_periodic_task
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.timing.monotonic import monotonic_ms
from models.catalog_locking import (
    enter_available_plugin_lifecycle_locks,
    enter_plugin_lifecycle_locks,
)
from models.discovery.database_update import (
    ModelDiscoveryUpdateDependencies,
    update_discovered_models_in_db,
)
from models.discovery.invalid_virtual_cleanup import cleanup_invalid_virtual_models
from models.discovery.provider_bounded_execution import PluginCheckUnchanged
from models.discovery.provider_execution import run_discovery_providers
from models.discovery.startup_phase import resolve_plugin_reconciliation_startup_blocker
from models.internal_protocols import ModelMutationEffectsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ModelDiscoveryService",
    "ModelDiscoveryServiceDependencies",
)

LOGGER_NAME = "SoAI.models.discovery.service"
OPERATION_MODEL_RUN_STARTUP_DISCOVERY = "models.discovery.service.model_run_startup_discovery"


@dataclass(frozen=True, slots=True)
class ModelDiscoveryServiceDependencies:
    config: ConfigProtocol
    database_models: DatabaseModelsProtocol
    plugin_manager: PluginManagerProtocol
    state_aggregator: StateAggregatorProtocol
    metrics: MetricsManagerProtocol
    mutation_effects: ModelMutationEffectsProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]
    shutdown_event: asyncio.Event
    installed_plugin_names_ref: Callable[[], set[str]]
    virtual_model_get: Callable[[str], Awaitable[VirtualModelConfig | None]]
    virtual_model_delete: Callable[[str], Awaitable[bool]]
    virtual_model_update: Callable[[str, JSONDict], Awaitable[VirtualModelConfig]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelDiscoveryServiceDependencies",
            config=self.config,
            database_models=self.database_models,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            metrics=self.metrics,
            model_record_locks=self.model_record_locks,
            mutation_effects=self.mutation_effects,
            plugin_manager=self.plugin_manager,
            shutdown_event=self.shutdown_event,
            state_aggregator=self.state_aggregator,
            virtual_model_delete=self.virtual_model_delete,
            virtual_model_get=self.virtual_model_get,
            virtual_model_update=self.virtual_model_update,
        )


class ModelDiscoveryService:

    def __init__(self, deps: ModelDiscoveryServiceDependencies) -> None:
        self._deps = deps
        self._update_lock = asyncio.Lock()
        self._discovery_lock = asyncio.Lock()
        self._discovery_rerun_requested = False
        self._pending_discovery_plugins: set[str] | None = set()
        self._pending_discovery_reuse_existing_models = True
        self.startup_discovery_complete_event = asyncio.Event()
        self._startup_discovery_result = StartupPhaseResult(StartupPhaseStatus.PENDING)
        self._startup_reconciliation_authoritative = False
        self._last_model_upsert_fingerprint: str | None = None
        self._disabled_discovery_logged: set[str] = set()
        self._download_discovery_logged: set[str] = set()
        self._update_deps = ModelDiscoveryUpdateDependencies(
            database_models=deps.database_models,
            plugin_manager=deps.plugin_manager,
            metrics=deps.metrics,
            mutation_effects=deps.mutation_effects,
            model_record_locks=deps.model_record_locks,
            virtual_model_get=deps.virtual_model_get,
            virtual_model_delete=deps.virtual_model_delete,
            virtual_model_update=deps.virtual_model_update,
        )

    @property
    def startup_discovery_result(self) -> StartupPhaseResult:
        return self._startup_discovery_result

    async def model_discover_all(
        self,
        plugins_to_scan: list[str] | None = None,
        *,
        reuse_existing_models_for_unloaded_plugins: bool = False,
        wait_for_completion: bool = False,
    ) -> None:
        if self._deps.shutdown_event.is_set():
            return
        if self._discovery_lock.locked() and not wait_for_completion:
            self._queue_discovery_rerun(
                plugins_to_scan,
                reuse_existing_models_for_unloaded_plugins,
            )
            return
        async with self._discovery_lock:
            while True:
                self._discovery_rerun_requested = False
                await self._run_discovery_once(
                    plugins_to_scan,
                    reuse_existing_models_for_unloaded_plugins=(
                        reuse_existing_models_for_unloaded_plugins
                    ),
                )
                if not self._discovery_rerun_requested or self._deps.shutdown_event.is_set():
                    return
                (
                    plugins_to_scan,
                    reuse_existing_models_for_unloaded_plugins,
                ) = self._consume_pending_discovery_rerun()

    def _queue_discovery_rerun(
        self,
        plugins_to_scan: list[str] | None,
        reuse_existing_models_for_unloaded_plugins: bool,
    ) -> None:
        had_pending_request = self._discovery_rerun_requested
        self._discovery_rerun_requested = True
        if plugins_to_scan is None:
            self._pending_discovery_plugins = None
        elif not had_pending_request:
            self._pending_discovery_plugins = set(plugins_to_scan)
        elif self._pending_discovery_plugins is not None:
            self._pending_discovery_plugins.update(plugins_to_scan)
        if not had_pending_request:
            self._pending_discovery_reuse_existing_models = (
                reuse_existing_models_for_unloaded_plugins
            )
        else:
            self._pending_discovery_reuse_existing_models = (
                self._pending_discovery_reuse_existing_models
                and reuse_existing_models_for_unloaded_plugins
            )

    def _consume_pending_discovery_rerun(self) -> tuple[list[str] | None, bool]:
        pending_plugins = self._pending_discovery_plugins
        pending_reuse = self._pending_discovery_reuse_existing_models
        self._pending_discovery_plugins = set()
        self._pending_discovery_reuse_existing_models = True
        if pending_plugins is None:
            return None, pending_reuse
        return sorted(pending_plugins), pending_reuse

    async def _run_discovery_once(
        self,
        plugins_to_scan: list[str] | None,
        *,
        reuse_existing_models_for_unloaded_plugins: bool,
        available_plugins_only: bool = False,
    ) -> None:
        self._deps.metrics.increment_counter("model_manager", "discoveries_run")
        start_time_ms = monotonic_ms()
        scan_plugins = (
            set(plugins_to_scan) if plugins_to_scan else self._deps.installed_plugin_names_ref()
        )
        async with AsyncExitStack() as plugin_lock_stack:
            if available_plugins_only:
                scan_plugins = await enter_available_plugin_lifecycle_locks(
                    plugin_lock_stack,
                    self._deps.plugin_manager.lifecycle,
                    scan_plugins,
                    timeout_seconds=RESPONSIVE_TIMEOUT_SEC,
                )
            else:
                await enter_plugin_lifecycle_locks(
                    plugin_lock_stack,
                    self._deps.plugin_manager.lifecycle,
                    scan_plugins,
                )
            if not scan_plugins:
                return
            existing_models = await self._deps.database_models.get_all_models_by_plugin()
            discovered_data = await run_discovery_providers(
                scan_plugins,
                self._deps.plugin_manager,
                self._deps.state_aggregator,
                existing_models,
                self._download_discovery_logged,
                self._disabled_discovery_logged,
                reuse_existing_models_for_unloaded_plugins=(
                    reuse_existing_models_for_unloaded_plugins
                ),
            )
            await self.model_update_in_db(discovered_data, existing_models)
        self._deps.metrics.record_timing(
            "model_manager",
            "timings",
            "discovery_duration_ms",
            duration_ms=float(monotonic_ms() - start_time_ms),
        )

    async def model_update_in_db(
        self,
        discovered_data: dict[
            str,
            dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
        ],
        existing_models: dict[str, dict[str, JSONDict]],
    ) -> None:
        async with self._update_lock:
            self._last_model_upsert_fingerprint = await update_discovered_models_in_db(
                self._update_deps,
                discovered_data,
                existing_models,
                (
                    self.startup_discovery_complete_event.is_set()
                    or self._startup_reconciliation_authoritative
                ),
                self._last_model_upsert_fingerprint,
            )

    async def model_cleanup_invalid_virtual(self) -> int:
        return await cleanup_invalid_virtual_models(
            self._deps.database_models,
            self._deps.virtual_model_delete,
        )

    async def model_run_startup_discovery(self) -> None:
        try:
            await self._deps.plugin_manager.wait_for_initial_reconciliation()
            plugin_result = self._deps.plugin_manager.initial_reconciliation_result
            startup_blocker = resolve_plugin_reconciliation_startup_blocker(plugin_result)
            if startup_blocker is not None:
                self._startup_discovery_result = startup_blocker
                return
            await self.model_cleanup_invalid_virtual()
            self._startup_reconciliation_authoritative = True
            try:
                await self.model_discover_all(
                    plugins_to_scan=list(self._deps.installed_plugin_names_ref()),
                    reuse_existing_models_for_unloaded_plugins=True,
                )
            finally:
                self._startup_reconciliation_authoritative = False
            self._startup_discovery_result = StartupPhaseResult(StartupPhaseStatus.SUCCESS)
        except asyncio.CancelledError:
            status = StartupPhaseStatus.FAILED
            message: str | None = "Initial model discovery was cancelled before shutdown."
            if self._deps.shutdown_event.is_set():
                status = StartupPhaseStatus.CANCELLED_BY_SHUTDOWN
                message = None
            self._startup_discovery_result = StartupPhaseResult(status, message)
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_MODEL_RUN_STARTUP_DISCOVERY,
            )
            log_exception(
                logger,
                coerced,
                message="Initial model discovery failed.",
                operation=OPERATION_MODEL_RUN_STARTUP_DISCOVERY,
            )
            self._startup_discovery_result = StartupPhaseResult(
                StartupPhaseStatus.FAILED,
                f"{type(coerced).__name__}: {coerced}",
            )
            raise
        finally:
            self.startup_discovery_complete_event.set()

    async def model_background_refresh_loop(self, refresh_interval_ms: int) -> None:
        logger = get_logger(LOGGER_NAME)
        await self.startup_discovery_complete_event.wait()
        await asyncio.sleep(RESPONSIVE_TIMEOUT_SEC)

        async def _run_refresh() -> None:
            if self._discovery_lock.locked():
                return
            async with self._discovery_lock:
                self._discovery_rerun_requested = False
                await self._run_discovery_once(
                    None,
                    reuse_existing_models_for_unloaded_plugins=True,
                    available_plugins_only=True,
                )
                while self._discovery_rerun_requested:
                    self._discovery_rerun_requested = False
                    plugins_to_scan, reuse_existing_models = self._consume_pending_discovery_rerun()
                    await self._run_discovery_once(
                        plugins_to_scan,
                        reuse_existing_models_for_unloaded_plugins=reuse_existing_models,
                    )

        await run_periodic_task(
            self._deps.shutdown_event,
            max(0.001, float(refresh_interval_ms) / 1000.0),
            _run_refresh,
            logger=logger,
            task_name="model_refresh_loop",
            run_immediately=False,
        )
