"""SoAI - Automation API payload schemas [backend/features/api/schemas/automations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from core.automation.automation_constants import AUTOMATION_OCCURRENCES_MAX_ITEMS
from core.errors.exceptions import ValidationError
from core.validation.strings import require_trimmed_text

__all__ = (
    "AutomationOccurrenceKey",
    "AutomationOccurrencesDelete",
)


class AutomationOccurrenceKey(BaseModel):
    automation_id: str = Field(..., min_length=1, max_length=255)
    scheduled_at_ms: int = Field(..., gt=0)

    @field_validator("automation_id")
    @classmethod
    def validate_automation_id(cls, value: str) -> str:
        return require_trimmed_text(value, "Automation occurrence automation_id cannot be empty.")

    @field_validator("scheduled_at_ms")
    @classmethod
    def validate_scheduled_at_ms(cls, value: int) -> int:
        if isinstance(value, bool) or value <= 0:
            raise ValidationError("Automation occurrence scheduled_at_ms is invalid.")
        return value


class AutomationOccurrencesDelete(BaseModel):
    occurrences: list[AutomationOccurrenceKey] = Field(
        ...,
        min_length=1,
        max_length=AUTOMATION_OCCURRENCES_MAX_ITEMS,
    )
