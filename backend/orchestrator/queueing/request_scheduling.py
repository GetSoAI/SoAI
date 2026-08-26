"""SoAI - Inference task scheduling key resolution [backend/orchestrator/queueing/request_scheduling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.orchestrator.request_priority import RequestSchedulingKey
from core.tasks.task import Task

__all__ = ("request_scheduling_key",)


def request_scheduling_key(task: Task) -> RequestSchedulingKey:
    assignment = task.require_orchestration_context().priority_assignment
    return RequestSchedulingKey(
        priority_order=assignment.priority_order,
        queued_at=assignment.queued_at,
        task_id=task.task_id,
    )
