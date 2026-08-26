"""SoAI - OpenAI assistant tool-call text length resolution [backend/core/openai/tool_call_text_lengths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.openai.reasoning_text import normalize_reasoning_text
from core.openai.tool_call_stream_matching import (
    THINKING_CLOSE_TAG_REGEX,
    THINKING_OPEN_TAG_REGEX,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_assistant_payload_text_lengths",
    "resolve_content_and_thinking_text_lengths",
    "resolve_message_text_lengths",
)


def _resolve_text_lengths_with_thinking_tags(text: str) -> tuple[int, int]:
    if not text:
        return (0, 0)
    visible_chars = 0
    thinking_chars = 0
    thinking_depth = 0
    cursor = 0
    while cursor < len(text):
        tag_index = text.find("<", cursor)
        if tag_index == -1:
            chunk = text[cursor:]
            if thinking_depth > 0:
                thinking_chars += len(chunk)
            else:
                visible_chars += len(chunk)
            break
        if tag_index > cursor:
            chunk = text[cursor:tag_index]
            if thinking_depth > 0:
                thinking_chars += len(chunk)
            else:
                visible_chars += len(chunk)
        close_index = text.find(">", tag_index + 1)
        if close_index == -1:
            chunk = text[tag_index:]
            if thinking_depth > 0:
                thinking_chars += len(chunk)
            else:
                visible_chars += len(chunk)
            break
        tag_text = text[tag_index : close_index + 1]
        normalized_tag = tag_text.lower()
        if re.match(THINKING_OPEN_TAG_REGEX, normalized_tag):
            thinking_depth += 1
        elif re.match(THINKING_CLOSE_TAG_REGEX, normalized_tag):
            if thinking_depth > 0:
                thinking_depth -= 1
        elif thinking_depth > 0:
            thinking_chars += len(tag_text)
        else:
            visible_chars += len(tag_text)
        cursor = close_index + 1
    return (visible_chars, thinking_chars)


def resolve_content_and_thinking_text_lengths(content: JSONValue | None) -> tuple[int, int]:
    if content is None:
        return (0, 0)
    if isinstance(content, str):
        return _resolve_text_lengths_with_thinking_tags(content)
    if isinstance(content, list):
        visible_chars = 0
        thinking_chars = 0
        for item in content:
            item_visible_chars, item_thinking_chars = resolve_content_and_thinking_text_lengths(
                item,
            )
            visible_chars += item_visible_chars
            thinking_chars += item_thinking_chars
        return (visible_chars, thinking_chars)
    if isinstance(content, dict):
        type_value = content.get("type")
        if isinstance(type_value, str) and type_value.strip().lower() in {"thinking", "reasoning"}:
            return (0, len(normalize_reasoning_text(content)))
        text_value = content.get("text")
        if isinstance(text_value, str):
            return _resolve_text_lengths_with_thinking_tags(text_value)
        value_value = content.get("value")
        if isinstance(value_value, str):
            return _resolve_text_lengths_with_thinking_tags(value_value)
        if "content" in content:
            return resolve_content_and_thinking_text_lengths(content.get("content"))
        if "parts" in content:
            return resolve_content_and_thinking_text_lengths(content.get("parts"))
    return (0, 0)


def resolve_message_text_lengths(message: JSONDict) -> tuple[int, int]:
    message_visible_chars, message_content_thinking_chars = (
        resolve_content_and_thinking_text_lengths(message.get("content"))
    )
    reasoning_payload = (
        message.get("reasoning_content")
        if "reasoning_content" in message
        else message.get("reasoning")
    )
    return (
        message_visible_chars,
        message_content_thinking_chars + len(normalize_reasoning_text(reasoning_payload)),
    )


def extract_assistant_payload_text_lengths(payload: JSONValue) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return (0, 0)
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return (0, 0)
    visible_chars = 0
    thinking_chars = 0
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        message_visible_chars, message_thinking_chars = resolve_message_text_lengths(message)
        visible_chars += message_visible_chars
        thinking_chars += message_thinking_chars
    return (visible_chars, thinking_chars)
