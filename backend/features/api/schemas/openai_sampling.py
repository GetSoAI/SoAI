"""SoAI - OpenAI sampling request schema fields [backend/features/api/schemas/openai_sampling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, StrictInt, field_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONValue
from features.api.schemas.openai_numeric_validation import reject_boolean_numeric_value

__all__ = ("SamplingRequestBase",)


class SamplingRequestBase(SoAIV1StrictModel):
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    frequency_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    logit_bias: dict[str, StrictInt] | None = None
    stop: str | list[str] | None = None
    top_p: float | None = Field(None, ge=0.0, le=1.0)

    @field_validator(
        "temperature",
        "frequency_penalty",
        "presence_penalty",
        "top_p",
        mode="before",
    )
    @classmethod
    def reject_boolean_float_fields(cls, value: JSONValue) -> JSONValue:
        return reject_boolean_numeric_value(value, message="Field must be numeric, not boolean.")

    @field_validator("logit_bias")
    @classmethod
    def validate_logit_bias_range(
        cls,
        value: dict[str, StrictInt] | None,
    ) -> dict[str, StrictInt] | None:
        if value is None:
            return None
        for token, bias in value.items():
            if not isinstance(token, str) or not token.strip():
                raise ValidationError("logit_bias keys must be non-empty strings.")
            if isinstance(bias, bool):
                raise ValidationError("logit_bias values must be integers.")
            if int(bias) < -100 or int(bias) > 100:
                raise ValidationError("logit_bias values must be between -100 and 100.")
        return value
