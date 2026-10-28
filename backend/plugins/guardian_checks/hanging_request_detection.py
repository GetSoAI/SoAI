"""SoAI - Guardian hanging request detection [backend/plugins/guardian_checks/hanging_request_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.metrics.keyspace_base import DIRECTOR_REQUESTS_PERSISTENT_PLUGIN_TIMEOUTS
from plugins.guardian.eligibility import GUARDIAN_LOGGER_NAME
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

if TYPE_CHECKING:
    from plugins.guardian.check_context import GuardianCheckContext

__all__ = ("check_hanging_requests",)


async def check_hanging_requests(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
    now: float,
    streaming_idle_timeout: float,
    non_streaming_timeout: float,
) -> dict[str, str]:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    plugins_to_recover: dict[str, str] = {}
    for info in check_context.active_inferences:
        plugin_name_value = info.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        plugin_name = plugin_name_value
        if plugin_name not in check_context.unlocked_plugins:
            continue
        dispatch_time_value = info.get("dispatch_time")
        if not isinstance(dispatch_time_value, int | float):
            continue
        dispatch_time = float(dispatch_time_value)
        is_streaming = info.get("is_streaming", False)
        streaming_request = is_streaming is True
        stream_activity_seen = info.get("stream_activity_seen", False) is True
        streaming_task = streaming_request or stream_activity_seen
        budget_deadline = info.get("initial_output_deadline_monotonic")
        if not stream_activity_seen and isinstance(budget_deadline, int | float):
            if info.get("execution_budget_source") == "caller_request" or now <= budget_deadline:
                continue
        health_watchdog = info.get("health_watchdog_sec")
        if not stream_activity_seen and isinstance(health_watchdog, int | float):
            timeout = float(health_watchdog)
            last_event = dispatch_time
        elif streaming_request and not stream_activity_seen:
            timeout = non_streaming_timeout
            last_event = dispatch_time
        elif stream_activity_seen:
            admitted_idle_timeout = info.get("streaming_idle_timeout_sec")
            timeout = (
                float(admitted_idle_timeout)
                if isinstance(admitted_idle_timeout, int | float) and admitted_idle_timeout > 0
                else streaming_idle_timeout
            )
            last_event_value = info.get("last_progress_time", dispatch_time)
            last_event = (
                float(last_event_value)
                if isinstance(last_event_value, int | float)
                else dispatch_time
            )
        else:
            timeout = non_streaming_timeout
            last_event = dispatch_time
        if not stream_activity_seen and isinstance(budget_deadline, int | float):
            timeout = max(0.0, float(budget_deadline) - dispatch_time)
        if now - last_event <= timeout:
            continue
        reason = (
            f"{'Streaming task idle' if streaming_task else 'Non-streaming task processing'} "
            f"for over {timeout}s."
        )
        task_id_value = info.get("task_id")
        task_id = str(task_id_value).strip() if task_id_value else "unknown"
        logger.warning(
            "Detected hanging task [%s] on plugin '%s'. Reason: %s. Triggering recovery.",
            task_id,
            plugin_name,
            reason,
        )
        if self.metrics and info.get("is_persistent") is True:
            self.metrics.increment_counter(
                *DIRECTOR_REQUESTS_PERSISTENT_PLUGIN_TIMEOUTS,
                plugin_name,
            )
        if plugin_name not in plugins_to_recover:
            plugins_to_recover[plugin_name] = reason
    return plugins_to_recover
