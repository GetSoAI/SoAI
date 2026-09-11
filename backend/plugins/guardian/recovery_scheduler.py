"""SoAI - Guardian recovery task scheduling [backend/plugins/guardian/recovery_scheduler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_base import DIRECTOR_REQUESTS_HEALTH_CHECK_RECOVERIES
from core.runtime.soai_identifiers import create_system_id
from core.state.plugin_state_generation import PluginStateGeneration
from plugins.guardian.check_context import GuardianCheckContext
from plugins.guardian.state_snapshot import build_guardian_plugin_state_snapshot
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

__all__ = ("schedule_guardian_recovery_tasks",)


async def schedule_guardian_recovery_tasks(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
    plugins_to_recover: dict[str, str],
    logger: LoggerProtocol,
) -> set[str]:
    if self.shutdown_event.is_set():
        return set()
    if not plugins_to_recover:
        return set()
    accepted_plugins: set[str] = set()
    async with self.recovery_initiation_lock:
        for plugin_name, reason in plugins_to_recover.items():
            if self.plugin_manager.lifecycle.is_plugin_locked(plugin_name):
                logger.info(
                    "Skipping recovery for '%s' as it is under a lifecycle operation.",
                    plugin_name,
                )
                continue
            expected_snapshot = check_context.plugin_states.get(plugin_name)
            current_states = build_guardian_plugin_state_snapshot(
                await self.state_aggregator.get_all_plugin_states(),
            )
            current_snapshot = current_states.get(plugin_name)
            if (
                expected_snapshot is None
                or expected_snapshot.last_updated_monotonic is None
                or current_snapshot != expected_snapshot
            ):
                logger.info(
                    "Skipping recovery for '%s' because its state generation changed from (%s, %s) to (%s, %s).",
                    plugin_name,
                    expected_snapshot.status if expected_snapshot is not None else None,
                    (
                        expected_snapshot.last_updated_monotonic
                        if expected_snapshot is not None
                        else None
                    ),
                    current_snapshot.status if current_snapshot is not None else None,
                    (
                        current_snapshot.last_updated_monotonic
                        if current_snapshot is not None
                        else None
                    ),
                )
                continue
            async with self.recovery_tasks_lock:
                if plugin_name in self.recovery_tasks:
                    continue
                if self.metrics:
                    self.metrics.increment_counter(
                        *DIRECTOR_REQUESTS_HEALTH_CHECK_RECOVERIES,
                        plugin_name,
                    )
                task = self.component_context.spawn_tracked_task(
                    self.guarded_recover_plugin(
                        plugin_name,
                        reason,
                        PluginStateGeneration(
                            status=expected_snapshot.status,
                            last_updated_monotonic=expected_snapshot.last_updated_monotonic,
                        ),
                    ),
                    name=f"plugin-guardian-recover-{plugin_name}",
                    logger=logger,
                    cancellation_binder=self.cancellation_binder,
                    finalizer_tracker=self.component_context.finalizer_tracker,
                    cancellation_id=create_system_id(
                        subsystem="plugin_guardian_recover",
                        owner=plugin_name,
                        include_random_suffix=True,
                    ),
                    owner="plugin_guardian_recovery",
                    metadata={"reason": reason},
                )
                self.recovery_tasks[plugin_name] = task
                accepted_plugins.add(plugin_name)
    return accepted_plugins
