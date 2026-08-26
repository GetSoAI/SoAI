"""SoAI - Plugin queue purge task partitioning [backend/orchestrator/control/plugin_queue_purge_partitioning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.model_info_fields import coerce_plugin_name
from core.tasks.task import Task

if TYPE_CHECKING:
    from orchestrator.queueing.internal_protocols import QueueServiceView
    from orchestrator.types import OrchestratorDependencies

__all__ = ("partition_tasks_by_primary_plugin",)

LOGGER_NAME = "SoAI.orchestrator.control.plugin_queue_purge_partitioning"
OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_QUEUE_PURGE_PARTITION_TASKS_BY_PRIMARY_PLUGIN = (
    "orchestrator.control.plugin_queue_purge.partition_tasks_by_primary_plugin"
)


async def partition_tasks_by_primary_plugin(
    *,
    orchestrator: OrchestratorDependencies,
    queue: QueueServiceView,
    plugin_name: str,
    tasks: list[Task],
    operation: str,
) -> tuple[list[Task], list[Task]]:
    logger = get_logger(LOGGER_NAME)
    universal_id_plugin_cache: dict[str, str | None] = {}
    to_requeue: list[Task] = []
    to_fail: list[Task] = []
    for task in tasks:
        context = queue.require_orchestration_context(task)
        execution_universal_ids = list(context.execution_universal_ids or [])
        if not execution_universal_ids:
            to_requeue.append(task)
            continue
        primary_universal_id = execution_universal_ids[0]
        if primary_universal_id in universal_id_plugin_cache:
            resolved_plugin_name = universal_id_plugin_cache[primary_universal_id]
        else:
            try:
                model_info = await orchestrator.model_information_service.model_get_info(
                    primary_universal_id,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=(
                        "Plugin queue purge failed to resolve model" f" [{primary_universal_id}]"
                    ),
                    operation=OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_QUEUE_PURGE_PARTITION_TASKS_BY_PRIMARY_PLUGIN,
                    details={
                        "operation": operation,
                        "plugin_name": plugin_name,
                        "universal_id": primary_universal_id,
                    },
                )
                resolved_plugin_name = None
            else:
                resolved_plugin_name = coerce_plugin_name(
                    model_info if isinstance(model_info, dict) else None,
                )
            universal_id_plugin_cache[primary_universal_id] = resolved_plugin_name
        if resolved_plugin_name == plugin_name:
            to_fail.append(task)
        else:
            to_requeue.append(task)
    return (to_requeue, to_fail)
