"""SoAI - Task list limit resolution [backend/core/tasks/list_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, NamedTuple

from core.config.numeric import coerce_positive_int
from core.config.protocols import ConfigProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "TaskListLimits",
    "resolve_task_list_limits",
)


class TaskListLimits(NamedTuple):
    max_limit: int
    default_limit: int
    max_offset: int


def resolve_task_list_limits(config: ConfigProtocol | Mapping[str, JSONValue]) -> TaskListLimits:
    max_limit_value: JSONValue = 1000
    default_limit_value: JSONValue = 1000
    max_offset_value: JSONValue = 10000
    if isinstance(config, ConfigProtocol):
        max_limit_value = config.get_int("SYSTEM.TASKS.TASK_LIST_MAX_LIMIT")
        default_limit_value = config.get_int("SYSTEM.TASKS.ACTIVE_TASKS_LIMIT")
        max_offset_value = config.get_int("SYSTEM.TASKS.TASK_LIST_MAX_OFFSET")
    else:
        max_limit_value = config.get("SYSTEM.TASKS.TASK_LIST_MAX_LIMIT", 1000)
        default_limit_value = config.get("SYSTEM.TASKS.ACTIVE_TASKS_LIMIT", max_limit_value)
        max_offset_value = config.get("SYSTEM.TASKS.TASK_LIST_MAX_OFFSET", 10000)
    max_limit = coerce_positive_int(max_limit_value, default=1000, minimum=1)
    default_limit = coerce_positive_int(default_limit_value, default=max_limit, minimum=1)
    max_offset = coerce_positive_int(max_offset_value, default=10000, minimum=0)
    return TaskListLimits(
        max_limit=max_limit,
        default_limit=default_limit,
        max_offset=max_offset,
    )
