"""SoAI - Orchestrator scheduler work-item enqueuing helper [backend/orchestrator/control/plugin_scheduler_work.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from core.orchestrator.scheduler_work import SchedulerWorkItem

__all__ = ("schedule_work_items",)

OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_SCHEDULER_WORK_SCHEDULE_WORK_ITEMS = (
    "orchestrator.control.plugin_scheduler_work.schedule_work_items"
)


LOGGER_NAME = "SoAI.orchestrator.control.plugin_scheduler_work"


async def schedule_work_items(
    *,
    scheduler: OrchestratorSchedulerProtocol,
    work_items: Sequence[SchedulerWorkItem],
    operation: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not work_items:
        return
    try:
        enqueue_tasks = [scheduler.queue_scheduler_work(work_item=item) for item in work_items]
        await asyncio.gather(*enqueue_tasks, return_exceptions=False)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to enqueue scheduler work items",
            operation=OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_SCHEDULER_WORK_SCHEDULE_WORK_ITEMS,
            details={"work_item_count": len(work_items), "operation": operation},
            level="warning",
        )
