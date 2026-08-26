"""SoAI - Bounded OpenAI prompt token counter [backend/core/openai/token_counter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from threading import Lock
from typing import TYPE_CHECKING

import tiktoken
from tiktoken.core import Encoding

from core.errors.exceptions import ValidationError
from core.openai.request_fields import resolve_optional_model_name
from core.openai.token_counter_chat_messages import count_chat_messages_tokens
from core.openai.token_counter_estimation import (
    apply_text_estimation_floor,
    resolve_counter_profile,
)
from core.openai.token_counter_inputs import count_input_tokens
from core.openai.token_counter_request_controls import count_request_level_controls
from core.openai.token_counter_types import (
    DEFAULT_MAX_COUNTED_TOKENS,
    DEFAULT_MAX_FIELD_CHARACTERS,
    DEFAULT_MAX_TOTAL_CHARACTERS,
    PromptTokenCountResult,
    PromptTokenCountState,
)
from core.openai.token_counting_limits import PromptTokenCountingLimits
from core.openai.token_estimation_profile import TokenEstimationProfile

if TYPE_CHECKING:
    from core.openai.prompt_counting_runtime import PromptCountingRuntime
    from core.openai.protocols import PromptTokenCountStateProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("PromptTokenCounter",)


class PromptTokenCounter:
    def __init__(
        self,
        default_encoding_name: str = "cl100k_base",
        *,
        max_field_characters: int = DEFAULT_MAX_FIELD_CHARACTERS,
        max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
        max_counted_tokens: int = DEFAULT_MAX_COUNTED_TOKENS,
        runtime: PromptCountingRuntime | None = None,
    ) -> None:
        if not default_encoding_name.strip():
            raise ValidationError("Token encoding name must be a non-empty string.")
        self._default_encoding_name = default_encoding_name.strip()
        self._encoding_cache: dict[str, Encoding] = {}
        self._encoding_cache_lock = Lock()
        self._limits = PromptTokenCountingLimits(
            max_field_characters=max_field_characters,
            max_total_characters=max_total_characters,
            max_counted_tokens=max_counted_tokens,
            encode_text=self._count_encoded_text,
        )
        self._runtime = runtime

    async def count_prompt_tokens_with_result_async(
        self,
        request_payload: JSONDict,
        *,
        profile: TokenEstimationProfile | None = None,
    ) -> PromptTokenCountResult:
        if self._runtime is None:
            raise ValidationError("Prompt token counting runtime is not configured.")
        invocation = partial(
            self.count_prompt_tokens_with_result,
            request_payload,
            profile=profile,
        )
        return await self._runtime.run(invocation)

    def shutdown(self) -> None:
        if self._runtime is not None:
            self._runtime.shutdown()

    async def run_blocking[*Arguments, ResultT](
        self,
        function: Callable[[*Arguments], ResultT],
        *args: *Arguments,
    ) -> ResultT:
        if self._runtime is None:
            raise ValidationError("Prompt token counting runtime is not configured.")
        return await self._runtime.run(function, *args)

    def _get_encoding(self, profile: TokenEstimationProfile) -> Encoding:
        encoding_name = profile.encoding_name.strip()
        cached = self._encoding_cache.get(encoding_name)
        if cached is not None:
            return cached
        with self._encoding_cache_lock:
            cached = self._encoding_cache.get(encoding_name)
            if cached is not None:
                return cached
            encoding = tiktoken.get_encoding(encoding_name)
            self._encoding_cache[encoding_name] = encoding
            return encoding

    def default_profile(self) -> TokenEstimationProfile:
        return TokenEstimationProfile.exact(self._default_encoding_name)

    @property
    def max_counted_tokens(self) -> int:
        return self._limits.max_counted_tokens

    def _count_encoded_text(self, value: str, encoding: Encoding) -> int:
        try:
            return len(encoding.encode(value, disallowed_special=()))
        except TypeError:
            return len(encoding.encode(value))

    def _count_request_controls(
        self,
        *,
        request_payload: JSONDict,
        encoding: Encoding,
        state: PromptTokenCountStateProtocol,
    ) -> int:
        return count_request_level_controls(
            request_payload=request_payload,
            encoding=encoding,
            state=state,
            count_texts=self._limits.count_texts,
            is_exhausted=self._limits.is_exhausted,
            max_field_characters=self._limits.max_field_characters,
        )

    def count_prompt_tokens_with_result(
        self,
        request_payload: JSONDict,
        *,
        profile: TokenEstimationProfile | None = None,
    ) -> PromptTokenCountResult:
        if not isinstance(request_payload, dict):
            raise ValidationError("Request payload must be a mapping.")
        state = PromptTokenCountState()
        prompt_tokens: int | None
        resolved_profile = resolve_counter_profile(
            profile=profile,
            model_name=resolve_optional_model_name(request_payload),
            default_encoding_name=self._default_encoding_name,
        )
        encoding = self._get_encoding(resolved_profile)
        messages = request_payload.get("messages")
        if isinstance(messages, list):
            prompt_tokens = count_chat_messages_tokens(
                messages=messages,
                max_total_characters=self._limits.max_total_characters,
                encoding=encoding,
                state=state,
                count_texts=self._limits.count_texts,
                is_exhausted=self._limits.is_exhausted,
            )
            prompt_tokens += self._count_request_controls(
                request_payload=request_payload,
                encoding=encoding,
                state=state,
            )
            return self._limits.build_result(
                prompt_tokens=prompt_tokens,
                state=state,
                profile=resolved_profile,
            )
        prompt = request_payload.get("prompt")
        if isinstance(prompt, list):
            prompt_tokens = self._limits.count_texts(
                (str(item) for item in prompt), encoding, state
            )
            prompt_tokens += self._count_request_controls(
                request_payload=request_payload,
                encoding=encoding,
                state=state,
            )
            return self._limits.build_result(
                prompt_tokens=prompt_tokens,
                state=state,
                profile=resolved_profile,
            )
        if isinstance(prompt, str):
            prompt_tokens = self._limits.count_texts([prompt], encoding, state)
            prompt_tokens += self._count_request_controls(
                request_payload=request_payload,
                encoding=encoding,
                state=state,
            )
            return self._limits.build_result(
                prompt_tokens=prompt_tokens,
                state=state,
                profile=resolved_profile,
            )
        input_value = request_payload.get("input")
        prompt_tokens = self._count_input_tokens(input_value, encoding, state)
        if prompt_tokens is None:
            return self._limits.build_result(
                prompt_tokens=None,
                state=state,
                profile=resolved_profile,
            )
        prompt_tokens += self._count_request_controls(
            request_payload=request_payload,
            encoding=encoding,
            state=state,
        )
        return self._limits.build_result(
            prompt_tokens=prompt_tokens,
            state=state,
            profile=resolved_profile,
        )

    def _count_input_tokens(
        self,
        input_value: JSONValue,
        encoding: Encoding,
        state: PromptTokenCountStateProtocol,
    ) -> int | None:
        return count_input_tokens(
            input_value=input_value,
            encoding=encoding,
            state=state,
            count_texts=self._limits.count_texts,
            count_chat_messages=(
                lambda messages, resolved_encoding, resolved_state: count_chat_messages_tokens(
                    messages=messages,
                    max_total_characters=self._limits.max_total_characters,
                    encoding=resolved_encoding,
                    state=resolved_state,
                    count_texts=self._limits.count_texts,
                    is_exhausted=self._limits.is_exhausted,
                )
            ),
            is_counting_exhausted=self._limits.is_exhausted,
        )

    def count_text_tokens(
        self,
        value: str,
        *,
        profile: TokenEstimationProfile | None = None,
        model_name: str | None = None,
    ) -> int:
        if not value:
            return 0
        resolved_profile = resolve_counter_profile(
            profile=profile,
            model_name=model_name,
            default_encoding_name=self._default_encoding_name,
        )
        encoding = self._get_encoding(resolved_profile)
        encoded_tokens = self._count_encoded_text(value, encoding)
        return apply_text_estimation_floor(
            token_count=encoded_tokens,
            character_count=len(value),
            profile=resolved_profile,
        )
