"""SoAI - Transcript completion token estimation helpers [backend/core/openai/usage/transcript_completion_token_estimation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.usage.tool_call_token_counting import count_openai_tool_call_tokens

if TYPE_CHECKING:
    from core.openai.protocols_usage import CompletionTokenTranscriptProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = ("estimate_transcript_completion_tokens",)


def estimate_transcript_completion_tokens(
    *,
    transcript: CompletionTokenTranscriptProtocol,
    prompt_token_counter: PromptTokenCounter,
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> int:
    completion_tokens = 0
    visible_text = transcript.get_visible_text()
    if visible_text:
        completion_tokens += prompt_token_counter.count_text_tokens(
            visible_text,
            model_name=model_name,
            profile=token_estimation_profile,
        )
    thinking_text = transcript.get_thinking_text()
    if thinking_text:
        completion_tokens += prompt_token_counter.count_text_tokens(
            thinking_text,
            model_name=model_name,
            profile=token_estimation_profile,
        )
    tool_calls = transcript.get_tool_calls()
    if tool_calls:
        completion_tokens += count_openai_tool_call_tokens(
            tool_calls=tool_calls,
            prompt_token_counter=prompt_token_counter,
            model_name=model_name,
            token_estimation_profile=token_estimation_profile,
        )
    return int(completion_tokens)
