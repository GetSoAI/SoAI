"""SoAI - Bounded prompt text token accumulation [backend/core/openai/token_counting_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable

from tiktoken.core import Encoding

from core.errors.exceptions import ValidationError
from core.openai.protocols import PromptTokenCountStateProtocol
from core.openai.token_counter_estimation import apply_text_estimation_floor, build_count_result
from core.openai.token_counter_types import (
    TERMINAL_CAP_REASONS,
    PromptTokenCountResult,
    PromptTokenCountState,
)
from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = ("PromptTokenCountingLimits",)


class PromptTokenCountingLimits:
    def __init__(
        self,
        *,
        max_field_characters: int,
        max_total_characters: int,
        max_counted_tokens: int,
        encode_text: Callable[[str, Encoding], int],
    ) -> None:
        if max_field_characters <= 0:
            raise ValidationError("max_field_characters must be a positive integer.")
        if max_total_characters <= 0:
            raise ValidationError("max_total_characters must be a positive integer.")
        if max_counted_tokens <= 0:
            raise ValidationError("max_counted_tokens must be a positive integer.")
        self.max_field_characters = max_field_characters
        self.max_total_characters = max_total_characters
        self.max_counted_tokens = max_counted_tokens
        self._encode_text = encode_text

    def mark_capped(self, state: PromptTokenCountStateProtocol, reason: str) -> None:
        if state.reason in TERMINAL_CAP_REASONS and reason not in TERMINAL_CAP_REASONS:
            state.capped = True
            return
        if reason in TERMINAL_CAP_REASONS:
            state.reason = reason
            state.capped = True
            return
        if not state.capped:
            state.reason = reason
            state.capped = True

    def is_exhausted(self, state: PromptTokenCountStateProtocol) -> bool:
        return state.reason in TERMINAL_CAP_REASONS

    def count_texts(
        self,
        values: Iterable[str],
        encoding: Encoding,
        state: PromptTokenCountStateProtocol,
    ) -> int:
        total_tokens = 0
        for value in values:
            if not value:
                continue
            total_tokens += self._count_text(value, encoding, state)
            if self.is_exhausted(state):
                break
        return total_tokens

    def _count_text(
        self,
        value: str,
        encoding: Encoding,
        state: PromptTokenCountStateProtocol,
    ) -> int:
        if not value or self.is_exhausted(state):
            return 0
        total_remaining = self.max_total_characters - state.counted_characters
        if total_remaining <= 0:
            self.mark_capped(state, "total_character_limit")
            return 0
        normalized_value = value
        if len(normalized_value) > self.max_field_characters:
            normalized_value = normalized_value[: self.max_field_characters]
            self.mark_capped(state, "field_character_limit")
        if len(normalized_value) > total_remaining:
            normalized_value = normalized_value[:total_remaining]
            self.mark_capped(state, "total_character_limit")
        token_remaining = self.max_counted_tokens - state.total_tokens
        if token_remaining <= 0:
            self.mark_capped(state, "token_limit")
            return 0
        encoded_tokens = self._encode_text(normalized_value, encoding)
        if encoded_tokens > token_remaining:
            state.total_tokens += token_remaining
            state.counted_characters += len(normalized_value)
            self.mark_capped(state, "token_limit")
            return token_remaining
        state.total_tokens += encoded_tokens
        state.counted_characters += len(normalized_value)
        return encoded_tokens

    def build_result(
        self,
        *,
        prompt_tokens: int | None,
        state: PromptTokenCountState,
        profile: TokenEstimationProfile,
    ) -> PromptTokenCountResult:
        resolved_prompt_tokens = prompt_tokens
        if resolved_prompt_tokens is not None:
            resolved_prompt_tokens = apply_text_estimation_floor(
                token_count=resolved_prompt_tokens,
                character_count=state.counted_characters,
                profile=profile,
            )
        if resolved_prompt_tokens is not None and resolved_prompt_tokens > self.max_counted_tokens:
            resolved_prompt_tokens = self.max_counted_tokens
            self.mark_capped(state, "token_limit")
        return build_count_result(
            prompt_tokens=resolved_prompt_tokens,
            state=state,
            profile=profile,
        )
