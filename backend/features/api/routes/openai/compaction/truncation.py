"""SoAI - Compaction message truncation [backend/features/api/routes/openai/compaction/truncation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import count_prompt_occupancy
from core.openai.truncation import build_prefix_truncation_text
from features.api.routes.openai.compaction.content import (
    coerce_content_to_text,
    project_message_for_summary,
)
from features.api.routes.openai.compaction.payload import build_summary_payload

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict

__all__ = (
    "prepare_messages_for_summary",
    "truncate_projected_message_to_fit",
)


def truncate_projected_message_to_fit(
    *,
    prompt_token_counter: PromptTokenCounter,
    model: str,
    system_prompt_text: str,
    message: JSONDict,
    max_prompt_tokens: int,
    max_output_tokens: int,
) -> JSONDict:
    payload = build_summary_payload(
        model=model,
        system_prompt_text=system_prompt_text,
        chunk=[message],
        max_output_tokens=max_output_tokens,
    )
    initial_occupancy = count_prompt_occupancy(
        prompt_token_counter=prompt_token_counter,
        request_payload=payload,
    )
    if not initial_occupancy.capped and int(initial_occupancy.prompt_tokens) <= max_prompt_tokens:
        return message
    content = message.get("content")
    content_text = content if isinstance(content, str) else coerce_content_to_text(content)
    low, high = 0, len(content_text)
    best: str | None = None
    while low <= high:
        mid = (low + high) // 2
        candidate_text = build_prefix_truncation_text(
            original=content_text,
            prefix_length=mid,
        )
        candidate_message = dict(message)
        candidate_message["content"] = candidate_text
        candidate_payload = build_summary_payload(
            model=model,
            system_prompt_text=system_prompt_text,
            chunk=[candidate_message],
            max_output_tokens=max_output_tokens,
        )
        candidate_occupancy = count_prompt_occupancy(
            prompt_token_counter=prompt_token_counter,
            request_payload=candidate_payload,
        )
        if (
            not candidate_occupancy.capped
            and int(candidate_occupancy.prompt_tokens) <= max_prompt_tokens
        ):
            best = candidate_text
            low = mid + 1
            continue
        high = mid - 1
    if best is None:
        raise ValidationError(
            "Unable to summarize: compaction token budget is too small to fit any message content.",
        )
    truncated_message = dict(message)
    truncated_message["content"] = best
    final_payload = build_summary_payload(
        model=model,
        system_prompt_text=system_prompt_text,
        chunk=[truncated_message],
        max_output_tokens=max_output_tokens,
    )
    final_occupancy = count_prompt_occupancy(
        prompt_token_counter=prompt_token_counter,
        request_payload=final_payload,
    )
    if final_occupancy.capped or int(final_occupancy.prompt_tokens) > max_prompt_tokens:
        raise ValidationError(
            "Unable to summarize: compaction token budget is too small to fit truncated message content.",
        )
    return truncated_message


def prepare_messages_for_summary(
    *,
    prompt_token_counter: PromptTokenCounter,
    model: str,
    system_prompt_text: str,
    messages: list[JSONDict],
    max_prompt_tokens: int,
    max_output_tokens: int,
) -> list[JSONDict]:
    prepared: list[JSONDict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        projected = project_message_for_summary(message)
        prepared.append(
            truncate_projected_message_to_fit(
                prompt_token_counter=prompt_token_counter,
                model=model,
                system_prompt_text=system_prompt_text,
                message=projected,
                max_prompt_tokens=max_prompt_tokens,
                max_output_tokens=max_output_tokens,
            ),
        )
    return prepared
