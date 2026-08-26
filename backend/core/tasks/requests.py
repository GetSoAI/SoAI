"""SoAI - Core task request models used across task protocols and implementations [backend/core/tasks/requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TaskTypeId

__all__ = ("TaskRegistryFilteredQueryRequest",)


@dataclass(frozen=True, slots=True)
class TaskRegistryFilteredQueryRequest:
    user_id: int | None = None
    status: TaskStatus | None = None
    task_type: TaskTypeId | None = None
    owner_type: str | None = None
    owner_id: str | None = None
    cancellation_id: str | None = None
    limit: int = 100
    offset: int = 0
