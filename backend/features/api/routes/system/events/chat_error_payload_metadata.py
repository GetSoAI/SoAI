"""SoAI - Chat WebSocket error payload metadata [backend/features/api/routes/system/events/chat_error_payload_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.token_accounting import PromptOccupancy, build_prompt_occupancy_snapshot
from core.types.json import JSONDict

__all__ = ("build_chat_error_payload_metadata",)


def _build_prompt_budget_exceeded_metadata(
    *,
    prompt_tokens: int,
    budget_tokens: int,
    include_usage_preview: bool,
) -> JSONDict:
    payload: JSONDict = {
        "user_message": (
            "Prompt is too large for the preserved agent context budget "
            f"({prompt_tokens}/{budget_tokens} tokens)."
        ),
        "details": {
            "type": "prompt_budget_exceeded",
            "prompt_tokens": prompt_tokens,
            "budget_tokens": budget_tokens,
            "limit_source": "agent_compaction",
        },
    }
    if include_usage_preview:
        payload["usage_preview"] = build_prompt_occupancy_snapshot(
            occupancy=PromptOccupancy(
                prompt_tokens=prompt_tokens,
                capped=False,
                capped_reason=None,
                precision="exact",
            ),
            context_window_tokens=None,
            source="prompt_budget_error",
            budget_tokens=budget_tokens,
        )
    return payload


def _build_prompt_budget_capped_metadata(*, reason: str, budget_tokens: int) -> JSONDict:
    return {
        "user_message": (
            "Prompt token counting hit the preserved agent context budget "
            f"before a safe fit could be confirmed ({budget_tokens} tokens)."
        ),
        "details": {
            "type": "prompt_budget_capped",
            "budget_tokens": budget_tokens,
            "limit_source": "agent_compaction",
            "cap_reason": reason,
        },
    }


def build_chat_error_payload_metadata(
    *,
    message: str,
    include_usage_preview: bool,
) -> JSONDict:
    context_overflow = extract_context_overflow_validation(message)
    if context_overflow is not None:
        return {
            "user_message": context_overflow.message,
            "details": context_overflow.to_details(),
        }
    exceeded_match = re.fullmatch(
        "Prompt exceeds compaction budget after preserving required context \\(prompt_tokens=(?P<prompt_tokens>\\d+), budget_tokens=(?P<budget_tokens>\\d+)\\)\\.",
        message,
    )
    if exceeded_match is not None:
        prompt_tokens = int(exceeded_match.group("prompt_tokens"))
        budget_tokens = int(exceeded_match.group("budget_tokens"))
        return _build_prompt_budget_exceeded_metadata(
            prompt_tokens=prompt_tokens,
            budget_tokens=budget_tokens,
            include_usage_preview=include_usage_preview,
        )
    capped_match = re.fullmatch(
        "Prompt token counting capped after compaction \\(reason=(?P<reason>[^,]+), budget_tokens=(?P<budget_tokens>\\d+)\\)\\.",
        message,
    )
    if capped_match is not None:
        return _build_prompt_budget_capped_metadata(
            reason=capped_match.group("reason"),
            budget_tokens=int(capped_match.group("budget_tokens")),
        )
    return {}
