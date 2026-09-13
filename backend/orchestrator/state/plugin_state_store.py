"""SoAI - Plugin state mutation and snapshot storage [backend/orchestrator/state/plugin_state_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.errors.exceptions import StateError
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.state.authoritative_state_ordering import is_stale_authoritative_state_event
from core.state.state_log_formatting import (
    format_state_for_log,
    format_state_transition_for_log,
)
from core.state.state_names import (
    PLUGIN_STATE_STOPPED,
    PluginRuntimeStateName,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strict_numbers import require_non_negative_int_strict
from orchestrator.state.dependencies import PluginStateStoreDependencies
from orchestrator.state.plugin_state_queries import (
    get_all_plugin_store_states,
    get_all_plugin_store_states_with_version,
    get_plugin_store_status,
    update_plugin_store_health_status,
)
from orchestrator.state.purged_plugin_retention import prune_purged_plugins
from orchestrator.state.snapshot_builder import (
    get_or_create_plugin_state,
)

if TYPE_CHECKING:
    from core.state.health_status import PluginHealthStatus
    from core.state.protocols import ImmutablePluginStates
    from orchestrator.state.internal_protocols import PluginStateLockRegistryProtocol

__all__ = ("PluginStateStore",)

LOGGER_NAME = "SoAI.orchestrator.state.plugin_state_store"


class PluginStateStore:
    def __init__(self, deps: PluginStateStoreDependencies) -> None:
        self._database_plugins = deps.database_plugins
        self.plugin_states: dict[str, JSONDict] = {}
        self._purged_plugins: dict[str, float] = {}
        self._next_purged_plugins_prune_at = 0.0
        self.global_lock = asyncio.Lock()
        self.plugin_locks: PluginStateLockRegistryProtocol = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=7200.0,
                max_size=500,
                cleanup_interval_seconds=600.0,
            ),
        )
        self.state_version = 0
        self.immutable_snapshot_cache: ImmutablePluginStates | None = None
        self.logger: TraceLogger = get_logger(LOGGER_NAME)

    def invalidate_snapshot_cache(self) -> None:
        self.immutable_snapshot_cache = None

    def _prune_purged_plugins(self, now_monotonic: float, *, force: bool = False) -> None:
        self._next_purged_plugins_prune_at = prune_purged_plugins(
            self._purged_plugins,
            now_monotonic,
            self._next_purged_plugins_prune_at,
            force=force,
        )

    async def bootstrap_from_database(self) -> None:
        all_plugins = await self._database_plugins.get_authoritative_plugin_states()
        records: list[tuple[str, str, int]] = []
        for plugin_record in all_plugins:
            plugin_name = plugin_record.get("plugin_name")
            persisted_state = plugin_record.get("state")
            if not isinstance(plugin_name, str) or not plugin_name:
                raise StateError("The stored plugin identity is invalid.")
            if not isinstance(persisted_state, str) or not persisted_state:
                raise StateError("The stored plugin state is invalid.")
            sequence = require_non_negative_int_strict(
                plugin_record.get("publication_sequence", 0),
                error_message="The stored state publication position is invalid.",
            )
            records.append((plugin_name, persisted_state, sequence))
        now_ms = int(epoch_ms())
        now_monotonic = time.monotonic()
        async with self.global_lock:
            for plugin_name, persisted_state, sequence in records:
                plugin_state = get_or_create_plugin_state(self.plugin_states, plugin_name)
                plugin_state.update(
                    {
                        "status": persisted_state,
                        "publication_sequence": sequence,
                        "authority": "database_bootstrap",
                        "reason": "Bootstrapped from database on startup",
                        "last_updated_ms": now_ms,
                        "last_updated_monotonic": now_monotonic,
                    },
                )
            if records:
                self.state_version += 1
                self.invalidate_snapshot_cache()
        self.logger.debug("Bootstrapped %s plugin states from database.", len(records))

    async def apply_state_change(
        self,
        event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
    ) -> bool:
        async with self.global_lock:
            current_monotonic = time.monotonic()
            self._prune_purged_plugins(current_monotonic)
            if event.plugin_name in self._purged_plugins:
                self.logger.trace(
                    "Ignoring state change for purged plugin '%s'",
                    event.plugin_name,
                )
                return False
        async with self.plugin_locks.lock(event.plugin_name):
            async with self.global_lock:
                current_monotonic = time.monotonic()
                self._prune_purged_plugins(current_monotonic)
                if event.plugin_name in self._purged_plugins:
                    self.logger.trace(
                        "Ignoring state change for purged plugin '%s'",
                        event.plugin_name,
                    )
                    return False
                current_state = self.plugin_states.get(event.plugin_name)
                if is_stale_authoritative_state_event(event, current_state):
                    return False
                current_state = get_or_create_plugin_state(
                    self.plugin_states,
                    event.plugin_name,
                )
                sequence_changed = (
                    current_state.get("publication_sequence", 0) != event.publication_sequence
                )
                previous_status = current_state.get("status")
                previous_authority = current_state.get("authority")
                previous_reason = current_state.get("reason")
                details_value = current_state.get("details")
                previous_details = dict(details_value) if isinstance(details_value, dict) else {}
                new_details = dict(previous_details)
                details_changed = False
                if (
                    isinstance(event, PluginRuntimeStateChangedEvent)
                    and isinstance(event.details, dict)
                    and event.details
                ):
                    for key, value in event.details.items():
                        if new_details.get(key) != value:
                            details_changed = True
                        new_details[key] = value
                if event.new_state == PLUGIN_STATE_STOPPED and new_details:
                    new_details = {}
                    details_changed = True
                status_changed = previous_status != event.new_state
                metadata_changed = (
                    sequence_changed
                    or previous_authority != event.authority
                    or previous_reason != event.reason
                    or details_changed
                )
                state_changed = status_changed or metadata_changed
                if not state_changed:
                    current_state.update(
                        {
                            "last_updated_ms": int(epoch_ms()),
                            "last_updated_monotonic": current_monotonic,
                        },
                    )
                    self.invalidate_snapshot_cache()
                    return False
                self.state_version += 1
                current_state.update(
                    {
                        "status": event.new_state,
                        "publication_sequence": event.publication_sequence,
                        "authority": event.authority,
                        "reason": event.reason,
                        "last_updated_ms": int(epoch_ms()),
                        "last_updated_monotonic": current_monotonic,
                    },
                )
                current_state["details"] = new_details
                self.invalidate_snapshot_cache()
                transition = (
                    format_state_transition_for_log(event.previous_state, event.new_state)
                    if status_changed
                    else f"{format_state_for_log(event.new_state)} (metadata update)"
                )
                if status_changed:
                    self.logger.info(
                        "State aggregated for '%s': %s (by %s)",
                        event.plugin_name,
                        transition,
                        event.authority,
                    )
                else:
                    self.logger.trace(
                        "State aggregated for '%s': %s (by %s)",
                        event.plugin_name,
                        transition,
                        event.authority,
                    )
                return status_changed

    async def apply_purge(self, plugin_name: str) -> bool:
        async with self.plugin_locks.lock(plugin_name), self.global_lock:
            current_monotonic = time.monotonic()
            self._purged_plugins[plugin_name] = current_monotonic
            self._prune_purged_plugins(current_monotonic, force=True)
            if self.plugin_states.pop(plugin_name, None):
                self.state_version += 1
                self.invalidate_snapshot_cache()
                self.logger.info("Purged state for deleted plugin '%s'.", plugin_name)
                return True
            return False

    async def clear_purged_status(self, plugin_name: str) -> None:
        async with self.global_lock:
            self._purged_plugins.pop(plugin_name, None)

    async def get_state_version(self) -> int:
        async with self.global_lock:
            return self.state_version

    async def get_all_states(self) -> ImmutablePluginStates:
        return await get_all_plugin_store_states(self)

    async def get_all_states_with_version(self) -> tuple[ImmutablePluginStates, int]:
        return await get_all_plugin_store_states_with_version(self)

    async def get_status(self, plugin_name: str) -> PluginRuntimeStateName:
        return await get_plugin_store_status(self, plugin_name)

    async def update_health_status(
        self,
        plugin_name: str,
        health_status: PluginHealthStatus,
    ) -> None:
        await update_plugin_store_health_status(self, plugin_name, health_status)

    async def get_health_statuses(self) -> dict[str, PluginHealthStatus]:
        async with self.global_lock:
            statuses: dict[str, PluginHealthStatus] = {}
            for plugin_name, plugin_state in self.plugin_states.items():
                details_value = plugin_state.get("details")
                if not isinstance(details_value, dict):
                    continue
                health_status = details_value.get("health_status")
                if health_status == "ok":
                    statuses[plugin_name] = "ok"
                elif health_status == "recovering":
                    statuses[plugin_name] = "recovering"
                elif health_status == "open":
                    statuses[plugin_name] = "open"
                elif health_status == "quarantined":
                    statuses[plugin_name] = "quarantined"
                elif health_status == "disabled":
                    statuses[plugin_name] = "disabled"
            return statuses
