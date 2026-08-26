"""SoAI - Orchestrator control status assembly [backend/orchestrator/control/status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorCapacityProtocol,
    VirtualModelHealthProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_orchestrator_status",)


async def get_orchestrator_status(
    *,
    disabled: bool,
    queue: QueueServiceView,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    active_inferences: OrchestratorActiveInferenceProtocol,
    capacity: OrchestratorCapacityProtocol,
    virtual_model_health: VirtualModelHealthProtocol,
) -> JSONDict:
    if disabled:
        return {
            "status": "DISABLED",
            "total_backlog_size": 0,
            "queued_tasks_count": 0,
            "pending_tasks_by_uid": {},
            "active_inferences": [],
            "active_inferences_count": 0,
            "deduplicated_tasks_count": 0,
            "idle_plugins_count": 0,
            "idle_plugins_list": [],
            "plugin_concurrency": {},
            "circuit_breakers": {},
            "last_deferral_reasons": {},
        }
    queue_status = await queue.get_status_snapshot()
    queue_status_json: JSONDict = {
        "queued_tasks_count": queue_status["queued_tasks_count"],
        "pending_tasks_by_uid": queue_status["pending_tasks_by_uid"],
        "deduplicated_tasks_count": queue_status["deduplicated_tasks_count"],
        "total_backlog_size": queue_status["total_backlog_size"],
        "last_deferral_reasons": queue_status["last_deferral_reasons"],
    }
    lifecycle_status = await lifecycle.watchers.get_status_snapshot()
    executor_status = await active_inferences.get_status_snapshot()
    capacity_status = await capacity.get_status_snapshot()
    virtual_models_health = await virtual_model_health.snapshot()
    status: JSONDict = {"status": "OPERATIONAL"}
    status.update(queue_status_json)
    status.update(executor_status)
    status.update(lifecycle_status)
    status["plugin_concurrency"] = capacity_status
    status["virtual_models_health"] = virtual_models_health
    return status
