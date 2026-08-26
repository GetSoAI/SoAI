"""SoAI - SoAI link content part shaping [backend/features/api/runtime/soai_links/content_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.workspaces.soai_path_link_codec import extract_soai_path_tokens

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "base_parts_with_single_text",
    "content_has_soai_path_tokens",
    "message_content_from_text_and_attachments",
    "message_content_parts",
    "message_copy",
    "raw_text_part",
    "split_finalized_message_content",
)


def message_copy(message: JSONDict) -> JSONDict:
    normalized = normalize_for_json(message)
    if not isinstance(normalized, dict):
        raise ValidationError("Message payload must be an object.")
    return dict(normalized)


def message_content_parts(content: JSONValue) -> list[JSONDict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not isinstance(content, list):
        raise ValidationError("Message content must be a string or array.")
    parts: list[JSONDict] = []
    for part in content:
        if not isinstance(part, dict):
            raise ValidationError("Message content part must be an object.")
        parts.append(dict(part))
    return parts


def raw_text_part(parts: list[JSONDict]) -> str | None:
    text_parts: list[str] = []
    for part in parts:
        if part.get("type") != "text":
            continue
        text_value = part.get("text")
        if not isinstance(text_value, str):
            raise ValidationError("Text content part must include text.")
        text_parts.append(text_value)
    if not text_parts:
        return None
    return "\n\n".join(text_parts)


def base_parts_with_single_text(parts: list[JSONDict], text: str) -> list[JSONDict]:
    base_parts: list[JSONDict] = []
    text_emitted = False
    for part in parts:
        if part.get("type") == "text":
            if text_emitted:
                continue
            next_part = dict(part)
            next_part["text"] = text
            base_parts.append(next_part)
            text_emitted = True
            continue
        base_parts.append(part)
    if not text_emitted:
        base_parts.insert(0, {"type": "text", "text": text})
    return base_parts


def content_has_soai_path_tokens(content: JSONValue) -> bool:
    if isinstance(content, str):
        return bool(extract_soai_path_tokens(content))
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        text_value = part.get("text")
        if isinstance(text_value, str) and extract_soai_path_tokens(text_value):
            return True
    return False


def message_content_from_text_and_attachments(
    text: str | None,
    attachment_content: list[JSONValue],
) -> list[JSONDict]:
    content: list[JSONDict] = []
    if isinstance(text, str) and text.strip():
        content.append({"type": "text", "text": text.strip()})
    for attachment_part in attachment_content:
        if not isinstance(attachment_part, dict):
            raise ValidationError("Input queue attachment content part must be an object.")
        content.append(dict(attachment_part))
    if not content:
        raise ValidationError("Input queue enqueue requires either text or attachment_content.")
    return content


def split_finalized_message_content(content: JSONValue) -> tuple[str | None, list[JSONValue]]:
    if isinstance(content, str):
        return (content if content.strip() else None), []
    if not isinstance(content, list):
        raise ValidationError("Finalized input queue content is invalid.")
    text_parts: list[str] = []
    attachment_content: list[JSONValue] = []
    for part in content:
        if not isinstance(part, dict):
            raise ValidationError("Finalized input queue content part is invalid.")
        if part.get("type") == "text":
            text_value = part.get("text")
            if not isinstance(text_value, str):
                raise ValidationError("Finalized input queue text part is invalid.")
            if text_value.strip():
                text_parts.append(text_value.strip())
            continue
        attachment_content.append(part)
    text = "\n\n".join(text_parts) if text_parts else None
    return text, attachment_content
