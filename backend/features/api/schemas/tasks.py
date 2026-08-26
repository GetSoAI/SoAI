"""SoAI - Task-related API schemas [backend/features/api/schemas/tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from core.validation.strings import require_trimmed_text

__all__ = (
    "CancelAllTasksPayload",
    "ReasonPayload",
)


class ReasonPayload(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Human-readable reason for the cancellation request.",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return require_trimmed_text(value, "Reason must not be empty.")


class CancelAllTasksPayload(ReasonPayload):
    include_internal: bool = Field(
        False,
        description=(
            "Set to true to cancel internal system tasks (e.g. maintenance jobs) "
            "alongside user-facing tasks."
        ),
    )
