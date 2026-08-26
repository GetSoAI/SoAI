"""SoAI - Orchestrator scheduler action and work item structures [backend/orchestrator/scheduling/actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.tasks.task import Task

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "SchedulerAction",
    "SchedulerActionType",
)


class SchedulerActionType(Enum):
    DISPATCH = 1
    RELOAD = 2
    START = 3
    EVICT_AND_START = 4


@dataclass(frozen=True, slots=True)
class SchedulerAction:
    priority_order: float
    action_type: SchedulerActionType
    universal_id: str
    plugin_name: str
    task: Task
    model_info: JSONDict
    victim_plugin: str | None = None
    pending_key: str | None = None
