"""SoAI - Auto-title prompt construction [backend/features/api/conversation_auto_title/prompt_template.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.default_title_resolution import (
    count_image_url_content_parts,
    resolve_first_text_content_part,
)
from core.prompts.system_prompts import render_text_prompt_template_v1

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_auto_title_prompt",)

_SUMMARY_MAX_CHARS = 240
_SUMMARY_TRUNCATED_CHARS = 237


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _truncate_summary(value: str) -> str:
    if len(value) <= _SUMMARY_MAX_CHARS:
        return value
    return f"{value[:_SUMMARY_TRUNCATED_CHARS]}..."


def _summarize_content(content: JSONValue) -> str:
    text = resolve_first_text_content_part(content)
    if text is not None:
        collapsed = _collapse_whitespace(text)
        if collapsed:
            return _truncate_summary(collapsed)
    return ""


def _summarize_user_message(user_message: JSONDict) -> str:
    content = user_message.get("content")
    text_summary = _summarize_content(content)
    if text_summary:
        return text_summary
    image_count = count_image_url_content_parts(content)
    if image_count == 1:
        return "Conversation started with one image."
    if image_count > 1:
        return f"Conversation started with {image_count} images."
    return "Conversation started."


def _summarize_assistant_message(assistant_message: JSONDict) -> str:
    summary = _summarize_content(assistant_message.get("content"))
    if summary:
        return summary
    return "No assistant reply content."


def build_auto_title_prompt(
    *,
    user_message: JSONDict,
    assistant_message: JSONDict,
) -> str:
    user_summary = _summarize_user_message(user_message)
    assistant_summary = _summarize_assistant_message(assistant_message)
    return render_text_prompt_template_v1(
        "conversation.auto_title.user_template.v1",
        {
            "AUTO_TITLE_USER_SUMMARY": user_summary,
            "AUTO_TITLE_ASSISTANT_SUMMARY": assistant_summary,
        },
    )
