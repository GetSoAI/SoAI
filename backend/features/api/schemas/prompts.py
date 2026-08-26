"""SoAI - Prompt API schemas [backend/features/api/schemas/prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from core.collections.ordered_uniqueness import unique_sequence
from core.errors.exceptions import ValidationError
from core.prompts.colors import validate_prompt_color
from core.validation.strings import require_trimmed_text

__all__ = (
    "PromptBatchDeleteRequest",
    "PromptCreate",
    "PromptUpdate",
)


class PromptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(default="")
    color: str | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return require_trimmed_text(value, "Prompt name cannot be empty.")

    @field_validator("content")
    @classmethod
    def default_content(cls, value: str) -> str:
        return value or ""

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        return validate_prompt_color(value)


class PromptUpdate(PromptCreate): ...


class PromptBatchDeleteRequest(BaseModel):
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[str]) -> list[str]:
        unique_ids = list(unique_sequence(value, omit_falsy=True))
        if not unique_ids:
            raise ValidationError("At least one prompt id must be provided.")
        return unique_ids
