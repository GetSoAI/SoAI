"""SoAI - Task route models [backend/features/api/routes/tasks/task_query_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel

from core.tasks.api_models import TaskQueryResponse

__all__ = (
    "SoftwareUpdateLogRequest",
    "TaskCancelRequest",
    "TaskListResponse",
)


class TaskListResponse(BaseModel):
    tasks: list[TaskQueryResponse]
    total_count: int
    limit: int
    offset: int


class TaskCancelRequest(BaseModel):
    reason: str = "User requested cancellation"


class SoftwareUpdateLogRequest(BaseModel):
    task_id: str
    from_version: str
    to_version: str
    status: str
    message: str | None = None
