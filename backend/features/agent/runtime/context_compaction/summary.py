"""SoAI - Context compaction summary message contract [backend/features/agent/runtime/context_compaction/summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.context_compaction_prompt_message import (
    normalize_context_compaction_prompt_message,
)
from features.agent.runtime.context_compaction.tag_blocks import extract_tag_block_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_context_compaction_placeholder_message",
    "build_summary_message",
    "extract_context_compaction_prompt_message",
    "extract_context_summary",
    "extract_summary_text_from_message",
    "is_context_summary_message",
    "strip_context_summary_messages",
    "wrap_context_summary_text",
)

_OPEN_TAG = "<context_summary>"
_CLOSE_TAG = "</context_summary>"
_PLACEHOLDER_CONTENT = "Context compacted."


def extract_summary_text_from_message(message: JSONDict) -> str | None:
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return extract_tag_block_text(content, open_tag=_OPEN_TAG, close_tag=_CLOSE_TAG)


def wrap_context_summary_text(summary: str) -> str:
    normalized = str(summary or "").strip()
    if not normalized:
        raise ValidationError("Summary content must be a non-empty string.")
    return f"{_OPEN_TAG}\n{normalized}\n{_CLOSE_TAG}"


def build_summary_message(summary: str) -> JSONDict:
    return {"role": "system", "content": wrap_context_summary_text(summary)}


def build_context_compaction_placeholder_message() -> JSONDict:
    return {"role": "system", "content": _PLACEHOLDER_CONTENT}


def _is_context_compaction_placeholder_message(message: JSONDict) -> bool:
    role_value = message.get("role")
    content_value = message.get("content")
    return role_value == "system" and content_value == _PLACEHOLDER_CONTENT


def extract_context_compaction_prompt_message(
    compacted_history: list[JSONDict],
) -> JSONDict | None:
    for message in compacted_history:
        if not (
            is_context_summary_message(message)
            or _is_context_compaction_placeholder_message(message)
        ):
            continue
        normalized = normalize_context_compaction_prompt_message(message)
        if normalized is not None:
            return normalized
    return None


def extract_context_summary(compacted_history: list[JSONDict]) -> str | None:
    for message in compacted_history:
        extracted = extract_summary_text_from_message(message)
        if extracted:
            return extracted
    return None


def is_context_summary_message(message: JSONDict) -> bool:
    return extract_summary_text_from_message(message) is not None


def strip_context_summary_messages(
    message_history: list[JSONDict],
) -> tuple[str | None, list[JSONDict]]:
    summaries: list[str] = []
    remaining: list[JSONDict] = []
    for message in message_history:
        extracted = extract_summary_text_from_message(message)
        if extracted is not None:
            summaries.append(extracted)
            continue
        remaining.append(message)
    combined = "\n".join(summary for summary in summaries if summary.strip()).strip()
    return (combined or None, remaining)
