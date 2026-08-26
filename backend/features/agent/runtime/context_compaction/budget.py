"""SoAI - Agent context compaction budget utilities [backend/features/agent/runtime/context_compaction/budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.content_text_rendering import render_openai_content_text
from core.openai.truncation import (
    SOAI_TRUNCATION_MARKER_TEXT,
    build_prefix_truncation_text,
)
from core.types.json import is_json_list
from features.agent.runtime.context_compaction.rewrite import rewrite_tool_message
from features.agent.runtime.context_compaction.summary import (
    extract_summary_text_from_message,
    is_context_summary_message,
    wrap_context_summary_text,
)
from features.agent.runtime.context_compaction.token_counting import (
    history_within_budget,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict, JSONValue

__all__ = ("truncate_message_content_to_fit_budget",)

_TEXT_SEGMENT_TYPES: frozenset[str] = frozenset(
    ("text", "input_text", "output_text", "summary_text", "reasoning_text"),
)


def _build_candidate_message_content(*, original: str, prefix_length: int) -> str:
    return build_prefix_truncation_text(original=original, prefix_length=prefix_length)


def _truncate_context_summary_to_fit_budget(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    updated_history: list[JSONDict],
    target_message: JSONDict,
    message_index: int,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None,
) -> list[JSONDict]:
    original_summary = extract_summary_text_from_message(target_message)
    if original_summary is None:
        updated_history[message_index] = target_message
        return updated_history
    summary_lines = original_summary.splitlines()
    low, high = 0, len(original_summary)
    best_content = wrap_context_summary_text(SOAI_TRUNCATION_MARKER_TEXT)
    while low <= high:
        mid = (low + high) // 2
        candidate_summary = _build_context_summary_candidate(
            original_summary=original_summary,
            summary_lines=summary_lines,
            suffix_length=mid,
        )
        candidate_message = dict(target_message)
        candidate_content = wrap_context_summary_text(candidate_summary)
        candidate_message["content"] = candidate_content
        candidate_history = list(updated_history)
        candidate_history[message_index] = candidate_message
        if history_within_budget(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=candidate_history,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        ):
            best_content = candidate_content
            low = mid + 1
            continue
        high = mid - 1
    final_message = dict(target_message)
    final_message["content"] = best_content
    updated_history[message_index] = final_message
    return updated_history


def _build_context_summary_candidate(
    *,
    original_summary: str,
    summary_lines: list[str],
    suffix_length: int,
) -> str:
    if suffix_length >= len(original_summary):
        return original_summary
    if not summary_lines:
        return SOAI_TRUNCATION_MARKER_TEXT
    remaining = max(0, suffix_length)
    kept_lines: list[str] = []
    for line in reversed(summary_lines):
        line_size = len(line) + (1 if kept_lines else 0)
        if kept_lines and line_size > remaining:
            break
        if not kept_lines and 0 < remaining < len(line):
            kept_lines.append(line[max(0, len(line) - remaining) :])
            break
        kept_lines.append(line)
        remaining -= line_size
        if remaining <= 0:
            break
    kept_lines.reverse()
    body = "\n".join(entry for entry in kept_lines if entry)
    marker = SOAI_TRUNCATION_MARKER_TEXT
    if not body:
        return marker
    return f"{marker}\n{body}"


def _normalize_content_part_type(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _extract_text_from_content_parts(content: list[JSONValue]) -> tuple[list[int], str]:
    text_indices: list[int] = []
    text_chunks: list[str] = []
    for index, entry in enumerate(content):
        if not isinstance(entry, dict):
            continue
        part_type = _normalize_content_part_type(entry.get("type"))
        if part_type is None:
            continue
        if part_type == "refusal":
            return ([], "")
        if part_type not in _TEXT_SEGMENT_TYPES:
            continue
        text_value = entry.get("text")
        if not isinstance(text_value, str):
            continue
        if not text_value:
            continue
        text_indices.append(index)
        text_chunks.append(text_value)
    return (text_indices, "\n".join(text_chunks))


def _build_truncated_content_parts(
    *,
    original_parts: list[JSONValue],
    text_indices: list[int],
    candidate_text: str,
) -> list[JSONValue]:
    text_index_set = set(text_indices)
    updated_parts: list[JSONValue] = []
    inserted = False
    for index, entry in enumerate(original_parts):
        if index not in text_index_set:
            updated_parts.append(entry)
            continue
        if inserted:
            continue
        updated_parts.append({"type": "text", "text": candidate_text})
        inserted = True
    if not inserted:
        return list(original_parts)
    return updated_parts


def truncate_message_content_to_fit_budget(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    message_index: int,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[JSONDict]:
    if message_index < 0 or message_index >= len(message_history):
        return message_history
    updated_history: list[JSONDict] = [dict(message) for message in message_history]
    target_message = dict(updated_history[message_index])
    if target_message.get("role") == "tool":
        updated_history[message_index] = rewrite_tool_message(target_message)
        return updated_history
    if "tool_calls" in target_message and isinstance(target_message.get("tool_calls"), list):
        target_message["tool_calls"] = []
        updated_history[message_index] = target_message
        if history_within_budget(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=updated_history,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        ):
            return updated_history
        target_message = dict(updated_history[message_index])
    if is_context_summary_message(target_message):
        return _truncate_context_summary_to_fit_budget(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            updated_history=updated_history,
            target_message=target_message,
            message_index=message_index,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        )
    content_value = target_message.get("content")
    if is_json_list(content_value):
        original_parts = content_value
        text_indices, original_text = _extract_text_from_content_parts(original_parts)
        if not text_indices or not original_text:
            updated_history[message_index] = target_message
            return updated_history
        low, high = 0, len(original_text)
        best_content = _build_candidate_message_content(original=original_text, prefix_length=0)
        while low <= high:
            mid = (low + high) // 2
            candidate_text = _build_candidate_message_content(
                original=original_text,
                prefix_length=mid,
            )
            candidate_message = dict(target_message)
            candidate_message["content"] = _build_truncated_content_parts(
                original_parts=original_parts,
                text_indices=text_indices,
                candidate_text=candidate_text,
            )
            candidate_history = list(updated_history)
            candidate_history[message_index] = candidate_message
            if history_within_budget(
                prompt_token_counter=prompt_token_counter,
                base_request_payload=base_request_payload,
                message_history=candidate_history,
                max_prompt_tokens=max_prompt_tokens,
                token_estimation_profile=token_estimation_profile,
            ):
                best_content = candidate_text
                low = mid + 1
                continue
            high = mid - 1
        final_message = dict(target_message)
        final_message["content"] = _build_truncated_content_parts(
            original_parts=original_parts,
            text_indices=text_indices,
            candidate_text=best_content,
        )
        updated_history[message_index] = final_message
        return updated_history
    original = render_openai_content_text(content_value)
    if not original:
        updated_history[message_index] = target_message
        return updated_history
    low, high = 0, len(original)
    best_content = _build_candidate_message_content(original=original, prefix_length=0)
    while low <= high:
        mid = (low + high) // 2
        candidate = _build_candidate_message_content(original=original, prefix_length=mid)
        candidate_message = dict(target_message)
        candidate_message["content"] = candidate
        candidate_history = list(updated_history)
        candidate_history[message_index] = candidate_message
        if history_within_budget(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=candidate_history,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        ):
            best_content = candidate
            low = mid + 1
            continue
        high = mid - 1
    final_message = dict(target_message)
    final_message["content"] = best_content
    updated_history[message_index] = final_message
    return updated_history
