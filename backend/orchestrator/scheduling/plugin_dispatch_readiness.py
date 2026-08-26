"""SoAI - Plugin dispatch readiness outcomes [backend/orchestrator/scheduling/plugin_dispatch_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.requeue_attempts import (
    build_scheduler_requeue_attempt_spec,
    execute_requeue_attempt,
)
from orchestrator.scheduling.plugin_readiness_gates import (
    resolve_deferred_warning_suffix,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.logging.rate_limited_logger import RateLimitedLogger
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from orchestrator.internal_protocols import OrchestratorTaskOutcomesProtocol
    from orchestrator.requeue_preparation import RequeueAttemptResult

__all__ = ("requeue_deferred_plugin_dispatch",)


async def requeue_deferred_plugin_dispatch(
    *,
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    outcomes: OrchestratorTaskOutcomesProtocol,
    task: Task,
    logger: LoggerProtocol,
    operation: str,
    warning_message: str,
    warning_args: tuple[str, ...],
    warner: RateLimitedLogger | None,
) -> RequeueAttemptResult:
    if warner is None:
        logger.warning(warning_message, *warning_args)
    else:
        suffix = resolve_deferred_warning_suffix(warner)
        if suffix is not None:
            logger.warning(warning_message, *warning_args, suffix)
    return await execute_requeue_attempt(
        queue,
        task_registry,
        task,
        spec=build_scheduler_requeue_attempt_spec(
            logger=logger,
            operation=operation,
        ),
        outcomes=outcomes,
    )
