"""SoAI - Pydantic schemas for atomic model OpenAI capability override replacement [backend/features/api/schemas/model_openai_capability_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from core.errors.exceptions import ValidationError
from core.openai.modalities import get_openai_capability_taxonomy

__all__ = (
    "ModelOpenAICapabilityOverrideSet",
    "ModelOpenAICapabilityOverridesReplace",
)

_MAX_TOKENS_PER_CATEGORY = 64
_MAX_TOKEN_LENGTH = 64


def _normalize_token_map(value: dict[str, list[str]]) -> dict[str, list[str]]:
    taxonomy = get_openai_capability_taxonomy()
    normalized: dict[str, list[str]] = {}
    for category, tokens in value.items():
        if category not in taxonomy:
            raise ValidationError(f"Unknown OpenAI capability category '{category}'.")
        if len(tokens) > _MAX_TOKENS_PER_CATEGORY:
            raise ValidationError(f"Too many OpenAI capability overrides for {category}.")
        category_tokens: list[str] = []
        for token in tokens:
            candidate = str(token or "").strip().lower()
            if not candidate or len(candidate) > _MAX_TOKEN_LENGTH:
                raise ValidationError(f"Invalid OpenAI capability token for {category}.")
            if candidate not in category_tokens:
                category_tokens.append(candidate)
        if category_tokens:
            normalized[category] = category_tokens
    return normalized


class ModelOpenAICapabilityOverrideSet(BaseModel):
    disabled: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    enabled: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])

    @model_validator(mode="after")
    def normalize_tokens(self) -> ModelOpenAICapabilityOverrideSet:
        self.disabled = _normalize_token_map(self.disabled)
        self.enabled = _normalize_token_map(self.enabled)
        return self


class ModelOpenAICapabilityOverridesReplace(BaseModel):
    overrides: ModelOpenAICapabilityOverrideSet
    expected: ModelOpenAICapabilityOverrideSet

    @model_validator(mode="after")
    def validate_membership(self) -> ModelOpenAICapabilityOverridesReplace:
        taxonomy = get_openai_capability_taxonomy()
        for tokens_by_category in (self.overrides.disabled, self.overrides.enabled):
            for category, tokens in tokens_by_category.items():
                for token in tokens:
                    if token not in taxonomy[category]:
                        raise ValidationError(f"Unknown OpenAI token '{token}' for {category}.")
        return self
