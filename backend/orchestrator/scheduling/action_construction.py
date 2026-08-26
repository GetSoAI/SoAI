"""SoAI - Scheduler action construction primitives [backend/orchestrator/scheduling/action_construction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from orchestrator.scheduling.actions import SchedulerAction, SchedulerActionType

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "SchedulerActionInputs",
    "build_dispatch_action",
    "build_evict_and_start_action",
    "build_reload_action",
    "build_scheduler_action",
    "build_start_action",
)


@dataclass(frozen=True, slots=True)
class SchedulerActionInputs:
    priority_order: float
    universal_id: str
    plugin_name: str
    task: Task
    model_info: JSONDict
    pending_key: str


def build_scheduler_action(
    inputs: SchedulerActionInputs,
    *,
    action_type: SchedulerActionType,
    victim_plugin: str | None = None,
) -> SchedulerAction:
    return SchedulerAction(
        priority_order=inputs.priority_order,
        action_type=action_type,
        universal_id=inputs.universal_id,
        plugin_name=inputs.plugin_name,
        task=inputs.task,
        model_info=inputs.model_info,
        pending_key=inputs.pending_key,
        victim_plugin=victim_plugin,
    )


def build_dispatch_action(inputs: SchedulerActionInputs) -> SchedulerAction:
    return build_scheduler_action(inputs, action_type=SchedulerActionType.DISPATCH)


def build_start_action(inputs: SchedulerActionInputs) -> SchedulerAction:
    return build_scheduler_action(inputs, action_type=SchedulerActionType.START)


def build_reload_action(inputs: SchedulerActionInputs) -> SchedulerAction:
    return build_scheduler_action(inputs, action_type=SchedulerActionType.RELOAD)


def build_evict_and_start_action(
    inputs: SchedulerActionInputs,
    *,
    victim_plugin: str,
) -> SchedulerAction:
    return build_scheduler_action(
        inputs,
        action_type=SchedulerActionType.EVICT_AND_START,
        victim_plugin=victim_plugin,
    )
