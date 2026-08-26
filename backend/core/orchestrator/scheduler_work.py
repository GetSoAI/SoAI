"""SoAI - Orchestrator scheduler work item types [backend/core/orchestrator/scheduler_work.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    type SchedulerWorkType = Literal[
        "EVALUATE_ALL",
        "EVALUATE_PLUGIN",
        "EVALUATE_ROUTING_KEY",
        "SHUTDOWN",
    ]

__all__ = ("SchedulerWorkItem",)

SCHEDULER_WORK_TYPE_EVALUATE_ALL: SchedulerWorkType = "EVALUATE_ALL"
SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN: SchedulerWorkType = "EVALUATE_PLUGIN"
SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY: SchedulerWorkType = "EVALUATE_ROUTING_KEY"
SCHEDULER_WORK_TYPE_SHUTDOWN: SchedulerWorkType = "SHUTDOWN"


class SchedulerWorkItem(NamedTuple):
    work_type: SchedulerWorkType
    key: str
