"""SoAI - Ask user interaction schemas [backend/features/api/schemas/ask_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.strings import require_labeled_text

__all__ = (
    "AskUserAnswer",
    "AskUserResolveRequest",
)


class AskUserAnswer(SoAIV1StrictModel):
    answers: list[str] = Field(min_length=1, max_length=7)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for answer_index, answer in enumerate(value):
            normalized_answer = answer.strip() if isinstance(answer, str) else ""
            if not normalized_answer:
                raise ValidationError(f"answers[{answer_index}] must be a non-empty string")
            normalized.append(normalized_answer)
        return normalized


class AskUserResolveRequest(SoAIV1StrictModel):
    action: Literal["submit", "cancel"]
    answers: dict[str, AskUserAnswer] | None = None

    @field_validator("answers")
    @classmethod
    def validate_answers(
        cls,
        value: dict[str, AskUserAnswer] | None,
    ) -> dict[str, AskUserAnswer] | None:
        if value is None:
            return None
        normalized: dict[str, AskUserAnswer] = {}
        for key, answer in value.items():
            normalized_key = key.strip() if isinstance(key, str) else ""
            if not normalized_key:
                continue
            normalized_key = require_labeled_text(
                normalized_key,
                field_label="answers key",
                suffix="must be a non-empty string.",
            )
            normalized[normalized_key] = answer
        return normalized
