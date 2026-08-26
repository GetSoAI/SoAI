"""SoAI - Task API response models [backend/core/tasks/api_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic.types import JsonValue

__all__ = ("TaskQueryResponse",)


class TaskQueryResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    user_id: int
    owner_id: str
    owner_type: str
    created_at_ms: int
    updated_at_ms: int
    completed_at_ms: int | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    progress_percent: float | None = None
    status_message: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    result: dict[str, JsonValue] | None = None
    error_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
