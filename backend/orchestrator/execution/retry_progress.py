"""SoAI - Orchestrator inference retry progress [backend/orchestrator/execution/retry_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.metrics.keyspace_paths_orchestrator import (
    ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_BY_EXCEPTION,
    ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_BY_PLUGIN,
    ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_TOTAL,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_status

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from orchestrator.execution.retry_policy import ExecutionRetryDecision

__all__ = ("log_retry_then_backoff",)


async def log_retry_then_backoff(
    exception: Exception,
    *,
    attempt: int,
    decision: ExecutionRetryDecision,
    metrics: MetricsManagerProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    plugin_name: str,
    logger: TraceLogger,
    retry_message: str,
) -> None:
    metrics.increment_counter(*ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_TOTAL)
    metrics.increment_counter(*ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_BY_PLUGIN, plugin_name)
    metrics.increment_counter(
        *ORCHESTRATOR_COUNTER_EXECUTION_RETRIES_BY_EXCEPTION,
        type(exception).__name__,
    )
    logger.warning(
        "%s Retrying after %.2fs (reason=%s).",
        retry_message % (task.task_id, attempt, decision.max_attempts, type(exception).__name__),
        decision.delay_seconds,
        decision.reason,
    )
    await update_status(
        task_registry,
        task.task_id,
        TaskStatus.PROCESSING,
        status_message=(
            f"Retrying inference after {decision.reason.replace('_', ' ')} "
            f"({attempt}/{decision.max_attempts})"
        ),
        progress_current=attempt,
        progress_total=decision.max_attempts,
        progress_details=serialize_json_compact_stable_strict(
            {
                "retry_delay_seconds": round(decision.delay_seconds, 3),
                "retry_attempt": attempt,
                "retry_max_attempts": decision.max_attempts,
                "retry_reason": decision.reason,
            },
        ),
        emit_progress_event=True,
    )
    await asyncio.sleep(decision.delay_seconds)
