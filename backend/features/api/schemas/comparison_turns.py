"""SoAI - Comparison turn schemas [backend/features/api/schemas/comparison_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, field_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.epoch import EPOCH_MS_MIN

__all__ = (
    "ComparisonTurnPreflightRequest",
    "ComparisonTurnPreflightResponse",
    "ComparisonTurnPreflightVariant",
)


class ComparisonTurnPreflightRequest(SoAIV1StrictModel):
    primary_model_id: str = Field(min_length=1, max_length=256)
    comparison_model_ids: list[str] = Field(default_factory=list, max_length=4)
    minimum_assistant_turn_at_ms: int | None = Field(default=None, ge=EPOCH_MS_MIN)

    @field_validator("primary_model_id")
    @classmethod
    def normalize_primary_model_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValidationError("primary_model_id must be a non-empty string.")
        return normalized

    @field_validator("comparison_model_ids")
    @classmethod
    def normalize_comparison_model_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for entry in value:
            model_id = entry.strip()
            if not model_id:
                raise ValidationError("comparison_model_ids entries must be non-empty strings.")
            normalized.append(model_id)
        return normalized


class ComparisonTurnPreflightVariant(SoAIV1StrictModel):
    model_variant_index: int = Field(ge=0)
    requested_model_id: str = Field(min_length=1, max_length=256)
    resolved_model_id: str = Field(min_length=1, max_length=256)
    assistant_at_ms: int = Field(ge=EPOCH_MS_MIN)


class ComparisonTurnPreflightResponse(SoAIV1StrictModel):
    assistant_turn_at_ms: int = Field(ge=EPOCH_MS_MIN)
    variants: list[ComparisonTurnPreflightVariant]
