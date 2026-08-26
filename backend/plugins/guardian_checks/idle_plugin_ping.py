"""SoAI - Guardian idle plugin pings [backend/plugins/guardian_checks/idle_plugin_ping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.guardian.candidates import is_persistent_plugin_instance
from plugins.guardian.eligibility import (
    GUARDIAN_LOGGER_NAME,
    collect_idle_ping_candidate_names,
)
from plugins.guardian_checks.plugin_instance_prefetch import prefetch_plugin_instances
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from plugins.guardian.check_context import GuardianCheckContext

__all__ = ("ping_idle_plugins",)

OPERATION_PLUGINS_GUARDIAN_CHECKS_PING_TASK_GET_PLUGIN_INSTANCE = (
    "plugins.guardian_checks.ping_task.get_plugin_instance"
)
OPERATION_PLUGIN_GUARDIAN_HEALTH_PING = "plugin_guardian.health_ping"
PLUGIN_HEALTH_PING_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (StateError,)


async def ping_idle_plugins(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
    ping_timeout: float,
    grace_period: float,
    now_monotonic: float,
) -> dict[str, str]:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    if self.shutdown_event.is_set():
        return {}
    plugins_to_recover: dict[str, str] = {}
    idle_entries = await self.orchestrator.watchers.get_idle_plugins_with_timestamps()
    ping_candidates = collect_idle_ping_candidate_names(
        check_context,
        idle_entries,
        grace_period=grace_period,
        now_monotonic=now_monotonic,
    )
    fetched = await prefetch_plugin_instances(
        self,
        ping_candidates.persistent_candidates,
        operation="plugin_guardian.prefetch_instance",
    )
    persistent_targets: list[str] = []
    prefetched_instances: dict[str, PluginInstanceProtocol] = {}
    for plugin_name in ping_candidates.persistent_candidates:
        instance = fetched.get(plugin_name)
        if instance is None:
            if plugin_name not in plugins_to_recover:
                plugins_to_recover[plugin_name] = "Health ping skipped due to instance error."
            continue
        if is_persistent_plugin_instance(instance):
            persistent_targets.append(plugin_name)
            prefetched_instances[plugin_name] = instance
    targets = ping_candidates.idle_plugins + persistent_targets

    async def ping_task(plugin_name: str) -> tuple[str, str | None]:
        if self.shutdown_event.is_set():
            return (plugin_name, None)
        plugin_instance = prefetched_instances.get(plugin_name)
        if plugin_instance is None:
            try:
                plugin_instance = await self.plugin_manager.get_plugin_instance(plugin_name)
            except PLUGIN_HEALTH_PING_EXCEPTIONS as exception:
                if self.shutdown_event.is_set():
                    return (plugin_name, None)
                log_exception(
                    logger,
                    exception,
                    message="Failed to fetch plugin instance during health ping.",
                    operation=OPERATION_PLUGINS_GUARDIAN_CHECKS_PING_TASK_GET_PLUGIN_INSTANCE,
                    details={"plugin_name": plugin_name},
                    level="warning",
                )
                return (plugin_name, f"Health ping skipped due to instance error: {exception}.")
        if plugin_instance is None:
            return (plugin_name, "Health ping skipped because plugin instance is unavailable.")
        try:
            if self.shutdown_event.is_set():
                return (plugin_name, None)
            is_healthy, message = await asyncio.wait_for(
                plugin_instance.health_ping(),
                timeout=ping_timeout,
            )
            if not is_healthy:
                raise StateError(f"Health ping failed: {message}")
            await self.orchestrator.circuit_breakers.record_cb_success(plugin_name)
            await self.orchestrator.watchers.clear_plugin_recovery_attempts(plugin_name)
            return (plugin_name, None)
        except PLUGIN_HEALTH_PING_EXCEPTIONS as exception:
            if self.shutdown_event.is_set():
                return (plugin_name, None)
            level = "debug" if isinstance(exception, asyncio.TimeoutError) else "warning"
            log_exception(
                logger,
                exception,
                message="Health ping failed",
                operation=OPERATION_PLUGIN_GUARDIAN_HEALTH_PING,
                details={"plugin_name": plugin_name, "timeout_sec": ping_timeout},
                level=level,
            )
            reason = (
                f"Health ping timed out after {ping_timeout}s."
                if isinstance(exception, asyncio.TimeoutError)
                else f"Health ping raised an exception: {exception}."
            )
            return (plugin_name, reason)

    ping_tasks = [ping_task(plugin_name) for plugin_name in targets]
    results = await asyncio.gather(*ping_tasks, return_exceptions=False)
    for plugin_name, reason in results:
        if reason:
            if plugin_name not in plugins_to_recover:
                plugins_to_recover[plugin_name] = reason
    return plugins_to_recover
