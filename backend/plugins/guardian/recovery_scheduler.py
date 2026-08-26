"""SoAI - Guardian recovery task scheduling [backend/plugins/guardian/recovery_scheduler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_base import DIRECTOR_REQUESTS_HEALTH_CHECK_RECOVERIES
from core.runtime.soai_identifiers import create_system_id
from core.state.state_transition_sets import ALL_TRANSIENT_STATES
from plugins.guardian.check_context import GuardianCheckContext
from plugins.guardian.state_snapshot import get_plugin_status
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
) -> None:
    if self.shutdown_event.is_set():
        return
    if not plugins_to_recover:
        return
    async with self.recovery_initiation_lock:
        for plugin_name, reason in plugins_to_recover.items():
            if self.plugin_manager.lifecycle.is_plugin_locked(plugin_name):
                logger.info(
                    "Skipping recovery for '%s' as it is under a lifecycle operation.",
                    plugin_name,
                )
                continue
            async with self.recovery_tasks_lock:
                current_status = get_plugin_status(check_context.plugin_states, plugin_name)
                if plugin_name in self.recovery_tasks or current_status in ALL_TRANSIENT_STATES:
                    continue
                if self.metrics:
                    self.metrics.increment_counter(
                        *DIRECTOR_REQUESTS_HEALTH_CHECK_RECOVERIES,
                        plugin_name,
                    )
                task = self.component_context.spawn_tracked_task(
                    self.guarded_recover_plugin(plugin_name, reason),
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
