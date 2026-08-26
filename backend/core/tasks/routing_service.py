"""SoAI - Task type routing service [backend/core/tasks/routing_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.tasks.command_routes import TaskCommandRoute
from core.tasks.type_catalog import (
    TASK_TYPE_BACKGROUND_JOB,
    TaskTypeId,
)

__all__ = (
    "TaskTypeRoutingService",
    "TaskTypeRoutingServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class TaskTypeRoutingServiceDependencies:
    command_routes: tuple[TaskCommandRoute, ...]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskTypeRoutingServiceDependencies",
            command_routes=self.command_routes,
        )


class TaskTypeRoutingService:
    __slots__ = ("_command_to_task_type_map",)

    def __init__(self, dependencies: TaskTypeRoutingServiceDependencies) -> None:
        self._command_to_task_type_map = {
            route.command_type: route.task_type for route in dependencies.command_routes
        }

    def get_task_type_for_command(self, command_class: type[Event]) -> TaskTypeId:
        return self._command_to_task_type_map.get(command_class, TASK_TYPE_BACKGROUND_JOB)
