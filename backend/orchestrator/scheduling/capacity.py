"""SoAI - Scheduler plugin concurrency capacity management [backend/orchestrator/scheduling/capacity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.plugins.protocols import PluginManagerProtocol
from core.types.json_value import copy_json_dict
from core.validation.integers import is_strict_int
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SchedulerCapacity",
    "SchedulerCapacityDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.capacity"


DEFAULT_CONCURRENCY_LIMIT: int = 4


@dataclass(frozen=True, slots=True)
class SchedulerCapacityDependencies:
    capacity: OrchestratorCapacityProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    plugin_manager: PluginManagerProtocol
    concurrency_config: JSONDict | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerCapacityDependencies",
            capacity=self.capacity,
            lifecycle=self.lifecycle,
            plugin_manager=self.plugin_manager,
        )


class SchedulerCapacity:
    def __init__(self, deps: SchedulerCapacityDependencies) -> None:
        self._deps = deps
        self._concurrency_config: JSONDict | None = deps.concurrency_config

    def update_config(self, concurrency_config: JSONDict | None) -> None:
        self._concurrency_config = (
            copy_json_dict(concurrency_config) if concurrency_config else None
        )

    def configured_concurrency_limit(self, plugin_name: str, *, require_positive: bool) -> int:
        logger = get_logger(LOGGER_NAME)
        config_snapshot = self._concurrency_config
        config: dict[str, JSONValue] = (
            dict(config_snapshot) if isinstance(config_snapshot, dict) else {}
        )
        per_plugin_raw = config.get("PER_PLUGIN")
        per_plugin = per_plugin_raw if isinstance(per_plugin_raw, dict) else {}
        candidate = per_plugin.get(plugin_name)
        if is_strict_int(candidate):
            if require_positive and candidate > 0:
                return candidate
            if not require_positive and candidate >= 0:
                return candidate
        default_value = (
            config.get("DEFAULT", DEFAULT_CONCURRENCY_LIMIT)
            if isinstance(config, dict)
            else DEFAULT_CONCURRENCY_LIMIT
        )
        if is_strict_int(default_value):
            default_int = default_value
        elif isinstance(default_value, float):
            default_int = int(default_value)
        elif isinstance(default_value, str):
            try:
                default_int = int(default_value)
            except ValueError:
                default_int = DEFAULT_CONCURRENCY_LIMIT
        else:
            default_int = DEFAULT_CONCURRENCY_LIMIT
        if default_int == DEFAULT_CONCURRENCY_LIMIT and default_value != DEFAULT_CONCURRENCY_LIMIT:
            logger.debug(
                "Invalid concurrency limit configured (default): %s. Using default: %s",
                default_value,
                DEFAULT_CONCURRENCY_LIMIT,
            )
        if require_positive:
            return default_int if default_int > 0 else DEFAULT_CONCURRENCY_LIMIT
        return default_int if default_int >= 0 else DEFAULT_CONCURRENCY_LIMIT

    def resolve_plugin_limit_for_fairness(self, plugin_name: str) -> int:
        limit = self._deps.capacity.get_plugin_limit(plugin_name)
        if is_strict_int(limit) and limit > 0:
            return limit
        return self.configured_concurrency_limit(plugin_name, require_positive=True)

    async def get_concurrency_limit_for_plugin(self, plugin_name: str) -> int:
        instance = await self._deps.plugin_manager.get_plugin_instance(plugin_name)
        if instance is not None:
            instance_limit = instance.MAX_CONCURRENT_REQUESTS
            if is_strict_int(instance_limit) and instance_limit >= 0:
                return instance_limit
        configured = self.configured_concurrency_limit(plugin_name, require_positive=False)
        return max(configured, 0)

    async def ensure_plugin_capacity(self, plugin_name: str) -> None:
        if not self._deps.capacity.requires_plugin_capacity_refresh(plugin_name):
            return
        limit = await self.get_concurrency_limit_for_plugin(plugin_name)
        await self._deps.capacity.ensure_plugin_capacity(plugin_name, limit, 1)

    async def snapshot_outstanding_counts(self, plugin_names: set[str]) -> dict[str, int]:
        if not plugin_names:
            return {}
        state_snapshot = await self._deps.lifecycle.watchers.get_plugin_states_snapshot(
            plugin_names,
        )
        queue_sizes = await self._deps.capacity.get_queue_sizes(list(plugin_names))
        outstanding: dict[str, int] = {}
        for name in plugin_names:
            state = state_snapshot.get(name)
            active = len(state.active_tasks) if state is not None else 0
            outstanding[name] = active + queue_sizes.get(name, 0)
        return outstanding
