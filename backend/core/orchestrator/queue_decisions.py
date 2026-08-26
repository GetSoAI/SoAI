"""SoAI - Orchestrator queue decision models [backend/core/orchestrator/queue_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "QueueDecision",
    "QueueDecisionType",
    "build_cancel_task_decision",
    "build_dispatch_candidate_decision",
    "build_fail_task_decision",
    "build_persistence_failed_task_decision",
    "build_plan_required_decision",
    "build_schedule_work_decision",
)


class QueueDecisionType(Enum):
    DISPATCH_CANDIDATE = "dispatch_candidate"
    FAIL_TASK = "fail_task"
    CANCEL_TASK = "cancel_task"
    SCHEDULE_WORK = "schedule_work"
    PLAN_REQUIRED = "plan_required"


@dataclass(frozen=True, slots=True)
class QueueDecision:
    decision_type: QueueDecisionType
    task: Task | None = None
    model_info: JSONDict | None = None
    plugin_name: str | None = None
    routing_key: str | None = None
    reason: str | None = None
    allow_failover: bool = True
    error_type: ErrorType | None = None
    work_item: SchedulerWorkItem | None = None
    from_queue: bool = False


def build_fail_task_decision(
    task: Task,
    reason: str,
    *,
    allow_failover: bool,
    error_type: ErrorType | None = None,
) -> QueueDecision:
    return QueueDecision(
        QueueDecisionType.FAIL_TASK,
        task=task,
        reason=reason,
        allow_failover=allow_failover,
        error_type=error_type,
    )


def build_persistence_failed_task_decision(task: Task) -> QueueDecision:
    return build_fail_task_decision(
        task=task,
        reason=TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
        allow_failover=False,
    )


def build_cancel_task_decision(
    task: Task,
    reason: str,
    *,
    error_type: ErrorType | None = None,
) -> QueueDecision:
    return QueueDecision(
        QueueDecisionType.CANCEL_TASK,
        task=task,
        reason=reason,
        allow_failover=False,
        error_type=error_type,
    )


def build_dispatch_candidate_decision(
    task: Task,
    *,
    model_info: JSONDict,
    plugin_name: str,
    routing_key: str,
    from_queue: bool,
) -> QueueDecision:
    return QueueDecision(
        QueueDecisionType.DISPATCH_CANDIDATE,
        task=task,
        model_info=model_info,
        plugin_name=plugin_name,
        routing_key=routing_key,
        from_queue=from_queue,
    )


def build_plan_required_decision(task: Task) -> QueueDecision:
    return QueueDecision(QueueDecisionType.PLAN_REQUIRED, task=task)


def build_schedule_work_decision(work_item: SchedulerWorkItem) -> QueueDecision:
    return QueueDecision(QueueDecisionType.SCHEDULE_WORK, work_item=work_item)
