"""SoAI - Guardian idle plugin reconciliation [backend/plugins/guardian_checks/idle_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.state.state_transition_sets import INTERRUPTIBLE_IDLE_STATES
from plugins.guardian.candidates import is_persistent_plugin_instance
from plugins.guardian.eligibility import GUARDIAN_LOGGER_NAME
from plugins.guardian.state_snapshot import get_last_updated_monotonic
from plugins.guardian_checks.plugin_instance_prefetch import prefetch_plugin_instances
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

if TYPE_CHECKING:
    from plugins.guardian.check_context import GuardianCheckContext

__all__ = ("reconcile_idle_plugins",)


async def reconcile_idle_plugins(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
) -> None:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    plugin_names = list(check_context.plugin_states.keys())
    fetched = await prefetch_plugin_instances(
        self,
        plugin_names,
        operation="plugins.guardian_checks.reconcile_idle_plugins.prefetch_instance",
    )
    persistent_plugins: set[str] = set()
    for name, inst in fetched.items():
        if is_persistent_plugin_instance(inst):
            persistent_plugins.add(name)
    plugin_states_snapshot = await self.orchestrator.watchers.get_plugin_states_snapshot()
    busy_plugins = {
        plugin_state.plugin_name
        for plugin_state in plugin_states_snapshot.values()
        if plugin_state.is_busy
    }
    ground_truth_idle = {
        plugin_name
        for plugin_name, plugin_data in check_context.plugin_states.items()
        if plugin_data.status in INTERRUPTIBLE_IDLE_STATES
        and plugin_name not in busy_plugins
        and plugin_name not in persistent_plugins
    }
    idle_snapshot = await self.orchestrator.watchers.get_idle_plugins_with_timestamps()
    currently_idle = {plugin_name for plugin_name, _ in idle_snapshot}
    missing = ground_truth_idle - currently_idle
    extra = currently_idle - ground_truth_idle
    if not (missing or extra):
        return
    now_monotonic = time.monotonic()
    if missing:
        logger.warning(
            "Reconciliation: Adding missing idle plugins to eviction pool: %s",
            sorted(missing),
        )
    if extra:
        logger.warning(
            "Reconciliation: Removing non-idle plugins from eviction pool: %s",
            sorted(extra),
        )
    add: dict[str, float] = {}
    for plugin_name in missing:
        last_updated_monotonic = get_last_updated_monotonic(
            check_context.plugin_states,
            plugin_name,
            default=now_monotonic,
        )
        add[plugin_name] = last_updated_monotonic
    await self.orchestrator.watchers.reconcile_idle_plugins(add=add, remove=extra)
