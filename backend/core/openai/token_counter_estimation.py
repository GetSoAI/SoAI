"""SoAI - Token counter estimation profile application [backend/core/openai/token_counter_estimation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

import tiktoken

from core.errors.exceptions import ValidationError
from core.openai.token_counter_types import (
    APPROXIMATE_CHARS_PER_TOKEN_FLOOR,
    PromptTokenCountResult,
    PromptTokenCountState,
)
from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = (
    "apply_text_estimation_floor",
    "build_count_result",
    "resolve_counter_profile",
)


def resolve_counter_profile(
    *,
    profile: TokenEstimationProfile | None,
    model_name: str | None,
    default_encoding_name: str,
) -> TokenEstimationProfile:
    if profile is not None:
        return profile
    if model_name is not None and model_name.strip():
        try:
            encoding_name = tiktoken.encoding_for_model(model_name.strip()).name
        except KeyError:
            return TokenEstimationProfile.approximate(
                encoding_name=default_encoding_name,
                chars_per_token_floor=APPROXIMATE_CHARS_PER_TOKEN_FLOOR,
            )
        return TokenEstimationProfile.exact(encoding_name)
    return TokenEstimationProfile.exact(default_encoding_name)


def apply_text_estimation_floor(
    *,
    token_count: int,
    character_count: int,
    profile: TokenEstimationProfile,
) -> int:
    if not profile.is_approximate:
        return int(token_count)
    chars_per_token_floor = profile.chars_per_token_floor
    if chars_per_token_floor is None:
        raise ValidationError("Approximate token profile is missing its character floor.")
    character_floor = math.ceil(character_count / chars_per_token_floor)
    return max(int(token_count), character_floor)


def build_count_result(
    *,
    prompt_tokens: int | None,
    state: PromptTokenCountState,
    profile: TokenEstimationProfile,
) -> PromptTokenCountResult:
    return PromptTokenCountResult(
        prompt_tokens=prompt_tokens,
        capped=state.capped,
        reason=state.reason,
        counted_characters=state.counted_characters,
        is_approximate=profile.is_approximate,
    )
