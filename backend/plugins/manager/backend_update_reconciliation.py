"""SoAI - Sequential backend update reconciliation supervisor [backend/plugins/manager/backend_update_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import (
    InstalledPluginsChangedEvent,
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.events.types_system import ConfigReloadedEvent, SoAIMainStateChangedEvent
from core.events.types_tasks import TaskStatusChangedEvent
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.notifications.system_admin_alerts import create_plugin_backend_update_admin_alert
from core.plugins.backend_update_records import (
    BACKEND_UPDATE_CONTAINMENT_REQUIRED,
    BackendUpdateRecord,
)
from core.plugins.errors import PluginIncompatibleError
from core.runtime.network_policy import is_offline_mode_enabled
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.booleans import parse_bool
from plugins.manager.backend_update_admission import backend_update_application_ready
from plugins.manager.backend_update_automatic import admit_automatic_backend_update
from plugins.manager.backend_update_checks import check_backend_update
from plugins.manager.backend_update_identity import capture_backend_update_identity
from plugins.manager.compatibility import ensure_plugin_compatible
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("BackendUpdateReconciliation", "BackendUpdateReconciliationDependencies")

OPERATION = "plugins.manager.backend_update_reconciliation"
RETRY_BASE_SECONDS = 300.0
RETRY_MAX_SECONDS = 3600.0
WAKE_EVENTS: tuple[type[Event], ...] = (
    InstalledPluginsChangedEvent,
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
    ConfigReloadedEvent,
    SoAIMainStateChangedEvent,
    TaskStatusChangedEvent,
)


@dataclass(frozen=True, slots=True)
class BackendUpdateReconciliationDependencies:
    manager: PluginManagerRuntimeProtocol
    runtime: RuntimeStateStoreProtocol
    notifications: DatabaseNotificationsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="BackendUpdateReconciliationDependencies",
            manager=self.manager,
            runtime=self.runtime,
            notifications=self.notifications,
        )


class BackendUpdateReconciliation:
    def __init__(self, deps: BackendUpdateReconciliationDependencies) -> None:
        self._deps = deps
        self._wake = deps.manager.state.catalog.backend_update_wake
        self._task: asyncio.Task[None] | None = None
        self._retry: dict[str, tuple[int, float, bool]] = {}
        self._cursor: str | None = None
        self._set_degraded(False)

    def _set_degraded(self, degraded: bool) -> None:
        catalog = self._deps.manager.state.catalog
        if catalog.backend_update_degraded != degraded:
            catalog.backend_update_degraded = degraded
            catalog.backend_update_publication_pending = True

    async def _on_wake(self, event: Event) -> None:
        if isinstance(event, TaskStatusChangedEvent) and event.new_status not in {
            "completed",
            "failed",
            "cancelled",
        }:
            return
        self._wake.set()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        manager = self._deps.manager
        acquired: list[type[Event]] = []
        try:
            if self._task is None:
                for event_type in WAKE_EVENTS:
                    manager.dependencies.infrastructure.event_bus.subscribe(
                        event_type, self._on_wake
                    )
                    acquired.append(event_type)
            self._task = manager.dependencies.infrastructure.task_helpers.spawn_tracked_task(
                self._run(),
                logger=manager.logger,
                name="plugin-backend-update-reconciliation",
                cancellation_binder=manager.lifecycle.cancellation_binder,
                cancellation_id=create_system_id(
                    subsystem="backend_updates", owner="reconciliation", include_random_suffix=False
                ),
                owner="backend_update_reconciliation",
                finalizer_tracker=manager.lifecycle.finalizer_tracker,
            )
        finally:
            if self._task is None:
                for event_type in acquired:
                    manager.dependencies.infrastructure.event_bus.unsubscribe(
                        event_type, self._on_wake
                    )

    async def shutdown(self) -> None:
        if self._task is None:
            return
        for event_type in WAKE_EVENTS:
            self._deps.manager.dependencies.infrastructure.event_bus.unsubscribe(
                event_type, self._on_wake
            )
        task = self._task
        self._task = None
        await await_background_task_shutdown(
            task,
            logger=self._deps.manager.logger,
            operation=OPERATION,
            message="Backend update reconciliation shutdown failed.",
        )

    async def _run(self) -> None:
        await self._deps.runtime.startup_ready_event.wait()
        await self._deps.runtime.startup_transition_complete_event.wait()
        self._wake.set()
        failures = 0
        while not self._deps.runtime.shutdown_event.is_set():
            self._wake.clear()
            delay: float | None = None
            try:
                runtime = self._deps.runtime
                if (
                    not runtime.repair_plane
                    and not runtime.restart_pending.is_set()
                    and not self._deps.manager.lifecycle.disabled
                ):
                    await self._deps.manager.require_ready()
                    if await backend_update_application_ready(self._deps.manager, runtime):
                        delay = await self._pass()
                failures = 0
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                self._set_degraded(True)
                delay = compute_exponential_backoff_seconds(
                    failures,
                    base_seconds=RETRY_BASE_SECONDS,
                    maximum_seconds=RETRY_MAX_SECONDS,
                    jitter_ratio=0.1,
                )
                failures += 1
                log_exception(
                    self._deps.manager.logger,
                    exception,
                    message="Backend update reconciliation is degraded and will retry.",
                    operation=OPERATION,
                )
                try:
                    await self._publish_pending()
                except HANDLED_RUNTIME_EXCEPTIONS as publication_error:
                    log_exception(
                        self._deps.manager.logger,
                        publication_error,
                        message="Backend update degraded status publication will retry.",
                        operation=OPERATION,
                    )
                try:
                    async with asyncio.timeout(delay):
                        await self._deps.runtime.shutdown_event.wait()
                except TimeoutError:
                    continue
                return
            if self._wake.is_set():
                continue
            try:
                async with asyncio.timeout(delay):
                    await self._wake.wait()
            except TimeoutError:
                continue

    def _schedule_retry(self, plugin_name: str, *, degraded: bool = True) -> float:
        previous = self._retry.get(plugin_name)
        attempt = previous[0] if previous else 0
        delay = compute_exponential_backoff_seconds(
            attempt,
            base_seconds=RETRY_BASE_SECONDS,
            maximum_seconds=RETRY_MAX_SECONDS,
            jitter_ratio=0.1,
        )
        self._retry[plugin_name] = (attempt + 1, time.monotonic() + delay, degraded)
        return delay

    async def _reconcile_plugin(self, plugin_name: str) -> float | None:
        manager = self._deps.manager
        database = manager.dependencies.databases.plugins
        before = await database.get_backend_update(plugin_name)
        if before is not None and before.failure_code == BACKEND_UPDATE_CONTAINMENT_REQUIRED:
            await check_backend_update(manager, plugin_name, refresh=False)
            before = await database.get_backend_update(plugin_name)
        async with manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
            plugin_name, operation=f"{OPERATION}.commit"
        ):
            identity = await capture_backend_update_identity(
                manager, plugin_name, require_loaded_hash=False
            )
            record: BackendUpdateRecord | None = await database.materialize_backend_update(identity)
        manager.state.catalog.backend_update_publication_pending = (
            manager.state.catalog.backend_update_publication_pending or record != before
        )
        delay: float | None = None
        if not is_offline_mode_enabled(manager.dependencies.infrastructure.runtime_flags):
            cooldown = await database.get_backend_update_cooldown()
            cooling_down = cooldown is not None and cooldown > epoch_ms()
            if cooling_down and cooldown is not None:
                delay = (cooldown - epoch_ms()) / 1000.0
            elif (
                record is not None
                and record.status in {"check_pending", "check_failed"}
                and record.failure_code
                not in {"not_implemented", "backend_absent", "invalid_response"}
            ):
                result = await check_backend_update(manager, plugin_name, refresh=False)
                error = result.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                if code in {"server_error", "verification_failed"}:
                    delay = self._schedule_retry(plugin_name)
                elif code in {"locked", "deferred", "superseded"}:
                    delay = self._schedule_retry(plugin_name, degraded=False)
                else:
                    self._retry.pop(plugin_name, None)
                record = await database.get_backend_update(plugin_name)
            if not cooling_down and record is not None and record.status == "update_available":
                await admit_automatic_backend_update(manager, record)
        current = await database.get_backend_update(plugin_name)
        manager.state.catalog.backend_update_publication_pending = (
            manager.state.catalog.backend_update_publication_pending or current != before
        )
        if current is not None and current.status == "update_available":
            await create_plugin_backend_update_admin_alert(
                self._deps.notifications,
                plugin_name=plugin_name,
                package_hash=current.identity.package_hash,
                display_name=await manager.get_plugin_display_name(plugin_name),
            )
        return delay

    async def _pass(self) -> float | None:
        manager = self._deps.manager
        candidates = await manager.dependencies.databases.plugins.get_all_listable_plugins()
        names = sorted(
            plugin_name
            for record in candidates
            if parse_bool(record.get("supports_backend_installation"), default=False)
            and isinstance(plugin_name := record.get("plugin_name"), str)
        )
        if self._cursor is not None:
            names = [name for name in names if name > self._cursor] + [
                name for name in names if name <= self._cursor
            ]
        delay: float | None = None
        degraded = False
        for plugin_name in names:
            self._cursor = plugin_name
            retry = self._retry.get(plugin_name)
            if retry is not None and retry[1] > time.monotonic():
                retry_remaining = retry[1] - time.monotonic()
                delay = retry_remaining if delay is None else min(delay, retry_remaining)
                degraded = degraded or retry[2]
                continue
            try:
                await ensure_plugin_compatible(manager, plugin_name)
                remaining = await self._reconcile_plugin(plugin_name)
                scheduled = self._retry.get(plugin_name)
                degraded = degraded or (scheduled is not None and scheduled[2])
            except PluginIncompatibleError:
                self._retry.pop(plugin_name, None)
                continue
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                degraded = True
                remaining = self._schedule_retry(plugin_name)
                log_exception(
                    manager.logger,
                    exception,
                    message="Plugin backend update reconciliation is deferred.",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                )
            if remaining is not None:
                delay = remaining if delay is None else min(delay, remaining)
        self._set_degraded(degraded)
        await self._publish_pending()
        return delay

    async def _publish_pending(self) -> None:
        manager = self._deps.manager
        if manager.state.catalog.backend_update_publication_pending:
            manager.state.catalog.backend_update_publication_pending = False
            published = False
            try:
                await manager.dependencies.infrastructure.event_bus.publish(
                    InstalledPluginsChangedEvent(
                        installed_plugin_names=manager.state.catalog.known_plugins
                    )
                )
                published = True
            finally:
                if not published:
                    manager.state.catalog.backend_update_publication_pending = True
