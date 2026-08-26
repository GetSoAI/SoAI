"""SoAI - OpenAI tool call token counting [backend/core/openai/usage/tool_call_token_counting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = ("count_openai_tool_call_tokens",)


def count_openai_tool_call_tokens(
    *,
    tool_calls: list[JSONDict],
    prompt_token_counter: PromptTokenCounter,
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> int:
    total = 0
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        call_id = tool_call.get("id")
        if isinstance(call_id, str) and call_id:
            total += prompt_token_counter.count_text_tokens(
                call_id,
                model_name=model_name,
                profile=token_estimation_profile,
            )
        call_type = tool_call.get("type")
        if isinstance(call_type, str) and call_type:
            total += prompt_token_counter.count_text_tokens(
                call_type,
                model_name=model_name,
                profile=token_estimation_profile,
            )
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, dict):
            continue
        function_name = function_payload.get("name")
        if isinstance(function_name, str) and function_name:
            total += prompt_token_counter.count_text_tokens(
                function_name,
                model_name=model_name,
                profile=token_estimation_profile,
            )
        function_arguments = function_payload.get("arguments")
        if isinstance(function_arguments, str) and function_arguments:
            total += prompt_token_counter.count_text_tokens(
                function_arguments,
                model_name=model_name,
                profile=token_estimation_profile,
            )
    return total
