"""SoAI - Scheduler loop critical failure handling [backend/orchestrator/scheduling/loop_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task_cancellation_ops import generate_system_cancellation_id

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from orchestrator.types import OrchestratorDependencies

__all__ = ("handle_scheduler_loop_failure",)

OPERATION = "orchestrator_scheduler.scheduler_loop"


def handle_scheduler_loop_failure(
    logger: LoggerProtocol,
    orchestrator_deps: OrchestratorDependencies,
    exception: BaseException,
) -> None:
    coerced_exception = coerce_to_soai_error(exception, operation=OPERATION)
    log_exception(
        logger,
        coerced_exception,
        message="Critical error in orchestrator scheduler loop",
        operation=OPERATION,
        level="critical",
    )
    _ = spawn_tracked_task(
        orchestrator_deps.bus.publish(
            SystemMainStateOverrideEvent(
                state=SoAIMainState.ERROR,
                duration_sec=10,
                reason=f"Critical error in Orchestrator scheduler: {coerced_exception.code}",
            ),
        ),
        name="state-override-broadcast",
        owner="state_override_broadcast",
        logger=logger,
        metadata={"source": "scheduler", "code": coerced_exception.code},
        cancellation_binder=orchestrator_deps.task_cancellation_binder,
        finalizer_tracker=orchestrator_deps.task_finalizer_tracker,
        cancellation_id=generate_system_cancellation_id("state_override_broadcast"),
    )
