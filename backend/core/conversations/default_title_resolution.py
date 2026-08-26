"""SoAI - Canonical conversation default title resolution [backend/core/conversations/default_title_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.workspaces.soai_path_link_codec import strip_soai_path_tokens

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "count_image_url_content_parts",
    "resolve_default_title_from_user_message",
    "resolve_first_soai_path_title",
    "resolve_first_text_content_part",
)

_DEFAULT_TITLE_MAX_CHARS = 50
_DEFAULT_TITLE_TRUNCATED_CHARS = 47
_DEFAULT_IMAGE_TITLE = "Image"
_DEFAULT_TITLE = "Conversation"


def resolve_first_text_content_part(content: JSONValue) -> str | None:
    if isinstance(content, str):
        stripped = strip_soai_path_tokens(content)
        return stripped or None
    if not isinstance(content, list):
        return None
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        text_value = part.get("text")
        if isinstance(text_value, str):
            stripped = strip_soai_path_tokens(text_value)
            if stripped:
                return stripped
    return None


def count_image_url_content_parts(content: JSONValue) -> int:
    if not isinstance(content, list):
        return 0
    image_count = 0
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image_url":
            image_count += 1
    return image_count


def resolve_first_soai_path_title(content: JSONValue) -> str | None:
    if not isinstance(content, list):
        return None
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "soai_path":
            continue
        title_value = part.get("title")
        if isinstance(title_value, str):
            stripped = title_value.strip()
            if stripped:
                return stripped
    return None


def resolve_default_title_from_user_message(message: JSONDict) -> str:
    text = resolve_first_text_content_part(message.get("content"))
    if text is not None:
        if len(text) <= _DEFAULT_TITLE_MAX_CHARS:
            return text
        return f"{text[:_DEFAULT_TITLE_TRUNCATED_CHARS]}..."
    soai_path_title = resolve_first_soai_path_title(message.get("content"))
    if soai_path_title is not None:
        if len(soai_path_title) <= _DEFAULT_TITLE_MAX_CHARS:
            return soai_path_title
        return f"{soai_path_title[:_DEFAULT_TITLE_TRUNCATED_CHARS]}..."
    image_count = count_image_url_content_parts(message.get("content"))
    if image_count == 1:
        return _DEFAULT_IMAGE_TITLE
    if image_count > 1:
        return f"Images ({image_count})"
    return _DEFAULT_TITLE
