"""SoAI - Inline attachment prompt steering detection [backend/features/agent/runtime/inline_attachment_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.inline_file_content_markers import (
    INLINE_FILE_CONTENT_BEGIN_MARKER,
)
from core.openai.message_content_parts import iter_message_content_parts
from core.prompts.system_prompts import get_text_prompt_v1
from features.agent.runtime.tool_prompt_filter import normalize_selected_tool_names

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_inline_attachment_tool_hint",
    "messages_contain_inline_attachment_content",
)

_INLINE_ATTACHMENT_READER_TOOL_NAMES = frozenset(
    ("read_image", "read_document", "read_file"),
)


def messages_contain_inline_attachment_content(messages: list[JSONDict]) -> bool:
    for part in iter_message_content_parts(messages):
        part_type = part.get("type")
        if part_type == "image_url":
            return True
        if part_type == "text":
            text_value = part.get("text")
            if isinstance(text_value, str) and INLINE_FILE_CONTENT_BEGIN_MARKER in text_value:
                return True
    return False


def build_inline_attachment_tool_hint(messages: list[JSONDict], tool_names: list[str]) -> str:
    readers = normalize_selected_tool_names(tool_names) & _INLINE_ATTACHMENT_READER_TOOL_NAMES
    if not readers:
        return ""
    if not messages_contain_inline_attachment_content(messages):
        return ""
    return get_text_prompt_v1("agent.tool_hints.attachments.inline_already_provided.v1")
