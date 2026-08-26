"""SoAI - Anthropic message content translation [backend/features/api/routes/anthropic/content_translation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.errors.exceptions import ValidationError
from core.files.image_signature import ALLOWED_IMAGE_CONTENT_TYPES, validate_image_signature
from core.network.urls import require_absolute_http_url
from core.serialization.base64_values import decode_base64_ascii
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from features.api.routes.anthropic.request_values import (
    invalid_anthropic_request,
    require_anthropic_dict,
    require_anthropic_text,
    require_anthropic_trimmed_string,
)

__all__ = ("translate_anthropic_messages", "translate_anthropic_text_blocks")

_CONTENT_BLOCK_SEPARATOR = "\n\n"


def _join_text_blocks(texts: list[str]) -> str:
    return _CONTENT_BLOCK_SEPARATOR.join(texts)


def translate_anthropic_text_blocks(value: str | Sequence[JSONValue], field: str) -> str:
    if isinstance(value, str):
        return require_anthropic_text(value, field)
    texts: list[str] = []
    for index, raw_block in enumerate(value):
        block = require_anthropic_dict(raw_block, f"{field}.{index}")
        if block.get("type") != "text":
            raise invalid_anthropic_request(f"{field}.{index}.type is unsupported.")
        texts.append(require_anthropic_text(block.get("text"), f"{field}.{index}.text"))
    return _join_text_blocks(texts)


def _translate_image_source(source: JSONDict) -> str:
    source_type = source.get("type")
    if source_type == "url":
        url = require_anthropic_trimmed_string(source.get("url"), "image.source.url")
        try:
            return require_absolute_http_url(url)
        except ValidationError as exception:
            raise invalid_anthropic_request(
                "image.source.url must be an absolute HTTP or HTTPS URL."
            ) from exception
    if source_type != "base64":
        raise invalid_anthropic_request("Only base64 and URL image sources are supported.")
    media_type = require_anthropic_trimmed_string(
        source.get("media_type"), "image.source.media_type"
    )
    if media_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise invalid_anthropic_request("image.source.media_type is unsupported.")
    data = require_anthropic_trimmed_string(source.get("data"), "image.source.data")
    try:
        image_bytes = decode_base64_ascii(data, error_message="Image data is not valid base64.")
    except ValidationError as exception:
        raise invalid_anthropic_request(
            "image.source.data must contain valid base64."
        ) from exception
    valid_signature, detected_media_type = validate_image_signature(image_bytes[:32])
    if not valid_signature or detected_media_type != media_type:
        raise invalid_anthropic_request("image.source.data does not match image.source.media_type.")
    return f"data:{media_type};base64,{data}"


def _translate_document(part: JSONDict) -> list[JSONDict]:
    source = require_anthropic_dict(part.get("source"), "document.source")
    source_type = source.get("type")
    title_value = part.get("title")
    title = (
        "Document" if title_value is None else require_anthropic_text(title_value, "document.title")
    )
    context_value = part.get("context")
    context = (
        None if context_value is None else require_anthropic_text(context_value, "document.context")
    )
    prefix = f"{title}\n{context}\n" if context is not None else f"{title}\n"
    if source_type == "text":
        data = require_anthropic_text(source.get("data"), "document.source.data")
        return [{"type": "text", "text": f"{prefix}{data}"}]
    if source_type == "content":
        content = source.get("content")
        if not isinstance(content, list):
            raise invalid_anthropic_request("document.source.content must be an array.")
        return [
            {
                "type": "text",
                "text": f"{prefix}{translate_anthropic_text_blocks(content, 'document.source.content')}",
            }
        ]
    if source_type == "base64":
        media_type = source.get("media_type")
        if media_type != "application/pdf":
            raise invalid_anthropic_request("document.source.media_type is unsupported.")
        data = require_anthropic_trimmed_string(source.get("data"), "document.source.data")
        try:
            document_bytes = decode_base64_ascii(
                data, error_message="Document data is not valid base64."
            )
        except ValidationError as exception:
            raise invalid_anthropic_request(
                "document.source.data must contain valid base64."
            ) from exception
        if not document_bytes.startswith(b"%PDF"):
            raise invalid_anthropic_request("document.source.data is not a PDF document.")
        file_part: JSONDict = {
            "type": "file",
            "file": {"filename": title, "file_data": f"data:application/pdf;base64,{data}"},
        }
        translated: list[JSONDict] = []
        if context is not None:
            translated.append({"type": "text", "text": context})
        translated.append(file_part)
        return translated
    raise invalid_anthropic_request("document.source.type is unsupported.")


def _tool_result(
    part: JSONDict, message_index: int, part_index: int
) -> tuple[JSONDict, list[JSONDict]]:
    field = f"messages.{message_index}.content.{part_index}"
    tool_use_id = require_anthropic_trimmed_string(part.get("tool_use_id"), f"{field}.tool_use_id")
    is_error_value = part.get("is_error", False)
    if not isinstance(is_error_value, bool):
        raise invalid_anthropic_request(f"{field}.is_error must be a boolean.")
    raw_result = part.get("content", "")
    text_parts: list[str] = []
    image_parts: list[JSONDict] = []
    if isinstance(raw_result, str):
        text_parts.append(raw_result)
    elif isinstance(raw_result, list):
        for result_index, raw_block in enumerate(raw_result):
            block = require_anthropic_dict(raw_block, f"{field}.content.{result_index}")
            if block.get("type") == "text":
                text_parts.append(
                    require_anthropic_text(
                        block.get("text"), f"{field}.content.{result_index}.text"
                    )
                )
            elif block.get("type") == "image":
                source = require_anthropic_dict(
                    block.get("source"), f"{field}.content.{result_index}.source"
                )
                image_parts.append(
                    {"type": "image_url", "image_url": {"url": _translate_image_source(source)}}
                )
            else:
                raise invalid_anthropic_request(
                    f"{field}.content.{result_index}.type is unsupported."
                )
    else:
        raise invalid_anthropic_request("tool_result.content must be text or content blocks.")
    result_text = _join_text_blocks(text_parts)
    if image_parts and not result_text:
        result_text = "Tool returned image content."
    if is_error_value:
        result_text = f"Tool execution failed:\n{result_text}"
    return {"role": "tool", "tool_call_id": tool_use_id, "content": result_text}, image_parts


def _user_content(parts: list[JSONValue], message_index: int) -> list[JSONDict]:
    if not parts:
        raise invalid_anthropic_request(
            f"messages.{message_index}.content must contain at least one block."
        )
    user_parts: list[JSONDict] = []
    tool_messages: list[JSONDict] = []
    for part_index, raw_part in enumerate(parts):
        part = require_anthropic_dict(raw_part, f"messages.{message_index}.content.{part_index}")
        part_type = part.get("type")
        if part_type == "text":
            user_parts.append(
                {"type": "text", "text": require_anthropic_text(part.get("text"), "text")}
            )
        elif part_type == "image":
            source = require_anthropic_dict(part.get("source"), "image.source")
            user_parts.append(
                {"type": "image_url", "image_url": {"url": _translate_image_source(source)}}
            )
        elif part_type == "document":
            user_parts.extend(_translate_document(part))
        elif part_type in {"tool_result", "mcp_tool_result"}:
            tool_message, result_images = _tool_result(part, message_index, part_index)
            tool_messages.append(tool_message)
            user_parts.extend(result_images)
        else:
            raise invalid_anthropic_request(f"Unsupported user content block type: {part_type}.")
    if user_parts:
        tool_messages.append({"role": "user", "content": user_parts})
    return tool_messages


def _assistant_message(parts: list[JSONValue], message_index: int) -> JSONDict:
    if not parts:
        raise invalid_anthropic_request(
            f"messages.{message_index}.content must contain at least one block."
        )
    texts: list[str] = []
    thinking_texts: list[str] = []
    tool_calls: list[JSONDict] = []
    has_thinking_block = False
    for part_index, raw_part in enumerate(parts):
        part = require_anthropic_dict(raw_part, f"messages.{message_index}.content.{part_index}")
        part_type = part.get("type")
        if part_type == "text":
            texts.append(require_anthropic_text(part.get("text"), "text"))
        elif part_type in {"tool_use", "server_tool_use", "mcp_tool_use"}:
            tool_calls.append(
                {
                    "id": require_anthropic_trimmed_string(part.get("id"), "tool_use.id"),
                    "type": "function",
                    "function": {
                        "name": require_anthropic_trimmed_string(part.get("name"), "tool_use.name"),
                        "arguments": serialize_json_compact_stable_strict(
                            require_anthropic_dict(part.get("input"), "tool_use.input")
                        ),
                    },
                }
            )
        elif part_type == "thinking":
            has_thinking_block = True
            thinking_texts.append(require_anthropic_text(part.get("thinking"), "thinking.thinking"))
            require_anthropic_trimmed_string(part.get("signature"), "thinking.signature")
        elif part_type == "redacted_thinking":
            has_thinking_block = True
            require_anthropic_trimmed_string(part.get("data"), "redacted_thinking.data")
        else:
            raise invalid_anthropic_request(
                f"Unsupported assistant content block type: {part_type}."
            )
    text_content = _join_text_blocks(texts)
    message: JSONDict = {
        "role": "assistant",
        "content": text_content if text_content or has_thinking_block else None,
    }
    if thinking_texts:
        message["reasoning_content"] = _join_text_blocks(thinking_texts)
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def translate_anthropic_messages(messages: list[JSONDict]) -> list[JSONDict]:
    translated: list[JSONDict] = []
    for message_index, message in enumerate(messages):
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system"}:
            raise invalid_anthropic_request(
                f"messages.{message_index}.role must be user, assistant, or system."
            )
        if role == "system":
            if not isinstance(content, str | list):
                raise invalid_anthropic_request(
                    f"messages.{message_index}.content must be text or an array."
                )
            translated.append(
                {
                    "role": "system",
                    "content": translate_anthropic_text_blocks(
                        content,
                        f"messages.{message_index}.content",
                    ),
                }
            )
        elif isinstance(content, str):
            translated.append(
                {
                    "role": role,
                    "content": require_anthropic_text(
                        content,
                        f"messages.{message_index}.content",
                    ),
                }
            )
        elif isinstance(content, list) and role == "user":
            translated.extend(_user_content(content, message_index))
        elif isinstance(content, list):
            translated.append(_assistant_message(content, message_index))
        else:
            raise invalid_anthropic_request(
                f"messages.{message_index}.content must be text or an array."
            )
    if not translated:
        raise invalid_anthropic_request("messages must contain translatable content.")
    return translated
