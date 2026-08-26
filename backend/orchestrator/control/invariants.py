"""SoAI - Orchestrator invariant monitoring loop [backend/orchestrator/control/invariants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_orchestrator import (
    ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION,
    ORCHESTRATOR_GAUGE_INVARIANT_PLUGIN_ACTIVE_DELTA,
    ORCHESTRATOR_GAUGE_INVARIANT_PROMPT_SLOT_DELTA,
    ORCHESTRATOR_GAUGE_OPEN_QUEUE_CYCLES,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.periodic import run_periodic_task
from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorCapacityProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("orchestrator_invariant_monitor_loop",)

LOGGER_NAME = "SoAI.orchestrator.control.invariants"
OPERATION = "orchestrator.invariants.check"


async def orchestrator_invariant_monitor_loop(
    *,
    queue: QueueServiceView,
    capacity: OrchestratorCapacityProtocol,
    active_inferences: OrchestratorActiveInferenceProtocol,
    metrics: MetricsManagerProtocol | None,
    shutdown_event: asyncio.Event,
    interval_seconds: float,
) -> None:
    logger = get_logger(LOGGER_NAME)

    async def _check() -> None:
        try:
            prompt_snapshot = queue.priority.get_prompt_slot_snapshot()
            tracked_prompt_slots = await queue.tracking.count_prompt_slot_active_tasks()
            held_value = int(prompt_snapshot.get("held", 0))
            delta = held_value - int(tracked_prompt_slots)
            if metrics is not None:
                metrics.set_gauge(*ORCHESTRATOR_GAUGE_INVARIANT_PROMPT_SLOT_DELTA, value=delta)
            if delta != 0:
                if metrics is not None:
                    metrics.increment_counter(*ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION)
                logger.warning(
                    "Invariant violation: prompt slot held delta=%s (held=%s tracked=%s enabled=%s limit=%s waiters=%s).",
                    delta,
                    held_value,
                    tracked_prompt_slots,
                    prompt_snapshot.get("enabled"),
                    prompt_snapshot.get("limit"),
                    prompt_snapshot.get("waiters"),
                )
            open_counts = queue.cycles.get_open_counts()
            if metrics is not None:
                for cycle_type, count in open_counts.items():
                    metrics.set_gauge(
                        *ORCHESTRATOR_GAUGE_OPEN_QUEUE_CYCLES,
                        cycle_type,
                        value=int(count),
                    )
            capacity_snapshot = await capacity.get_status_snapshot()
            plugin_names = [
                name
                for name, value in capacity_snapshot.items()
                if name and isinstance(value, dict)
            ]
            for plugin_name in plugin_names:
                plugin_state = capacity_snapshot.get(plugin_name)
                if not isinstance(plugin_state, dict):
                    continue
                capacity_active = plugin_state.get("active")
                if not isinstance(capacity_active, int):
                    continue
                active_count = await active_inferences.get_active_task_count(plugin_name)
                plugin_delta = int(capacity_active) - int(active_count)
                if metrics is not None:
                    metrics.set_gauge(
                        *ORCHESTRATOR_GAUGE_INVARIANT_PLUGIN_ACTIVE_DELTA,
                        plugin_name,
                        value=plugin_delta,
                    )
                if plugin_delta != 0:
                    if metrics is not None:
                        metrics.increment_counter(*ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION)
                    logger.warning(
                        "Invariant violation: plugin '%s' active delta=%s (capacity_active=%s active_inferences=%s).",
                        plugin_name,
                        plugin_delta,
                        capacity_active,
                        active_count,
                    )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Invariant monitor check failed (non-critical).",
                operation=OPERATION,
                level="debug",
            )

    await run_periodic_task(
        shutdown_event,
        float(interval_seconds),
        _check,
        logger=logger,
        task_name="orchestrator_invariant_monitor",
    )
