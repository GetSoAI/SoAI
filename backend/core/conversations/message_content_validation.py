"""SoAI - WebUI message content validation [backend/core/conversations/message_content_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
    validate_soai_file_unavailable_content_part,
    validate_soai_knowledge_content_part,
    validate_soai_knowledge_unavailable_content_part,
)
from core.conversations.content_part_validation_primitives import (
    require_content_part_dict,
    require_content_part_string,
)
from core.errors.exceptions import ValidationError
from core.openai.message_content_validation import validate_message_content_json
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part
from core.workspaces.soai_path_text_validation import validate_no_raw_soai_path_tokens

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("validate_webui_message_content_json",)


def _validate_strict_openai_part(part: JSONDict, *, param_prefix: str) -> JSONDict:
    validated = validate_message_content_json([part], param_prefix=param_prefix)
    if not isinstance(validated, list) or len(validated) != 1:
        raise ValidationError("Message content part is invalid.")
    return validated[0]


def _part_type(part: JSONDict, *, index: int) -> str:
    part_type_value = part.get("type")
    if not isinstance(part_type_value, str) or part_type_value != part_type_value.strip():
        raise ValidationError(f"Content part at index {index} has invalid type.")
    if not part_type_value:
        raise ValidationError(f"Content part at index {index} has invalid type.")
    return part_type_value


def _validate_content_part(
    part: JSONDict,
    *,
    role: str,
    index: int,
    param_prefix: str,
) -> JSONDict:
    part_type = _part_type(part, index=index)
    if part_type == "soai_path":
        if role != "user":
            raise ValidationError("SoAI path content parts are only valid on user messages.")
        return validate_soai_path_content_part(part)
    if part_type == "soai_file":
        if role != "user":
            raise ValidationError("SoAI file content parts are only valid on user messages.")
        return validate_soai_file_content_part(part)
    if part_type == "soai_knowledge":
        if role != "user":
            raise ValidationError("SoAI knowledge content parts are only valid on user messages.")
        return validate_soai_knowledge_content_part(part)
    if part_type == "soai_file_unavailable":
        if role != "user":
            raise ValidationError("Unavailable SoAI file parts are only valid on user messages.")
        return validate_soai_file_unavailable_content_part(part)
    if part_type == "soai_knowledge_unavailable":
        if role != "user":
            raise ValidationError(
                "Unavailable SoAI knowledge parts are only valid on user messages.",
            )
        return validate_soai_knowledge_unavailable_content_part(part)
    if role in ("system", "developer", "tool") and part_type != "text":
        raise ValidationError("Content part type is not allowed for this role.")
    if role == "assistant" and part_type not in ("text", "refusal"):
        raise ValidationError("Content part type is not allowed for this role.")
    if role == "user" and part_type not in ("text", "image_url", "input_audio", "file"):
        raise ValidationError("Content part type is not allowed for this role.")
    if part_type == "text" and role == "user":
        require_content_part_string(
            part.get("text"),
            message="Text content part must include text.",
            allow_empty=True,
        )
        return dict(part)
    return _validate_strict_openai_part(part, param_prefix=f"{param_prefix}[{index}]")


def validate_webui_message_content_json(
    content_value: JSONValue,
    *,
    role: str,
    param_prefix: str = "content",
) -> str | list[JSONDict]:
    if isinstance(content_value, str):
        if role not in ("assistant", "tool") and not content_value.strip():
            raise ValidationError("Message content must be semantically non-empty.")
        validate_no_raw_soai_path_tokens(content_value)
        return content_value
    if not isinstance(content_value, list):
        raise ValidationError("Message content must be string or array of content parts.")
    if not content_value:
        raise ValidationError("Message content array cannot be empty.")
    validated_parts: list[JSONDict] = []
    text_parts: list[str] = []
    soai_path_parts: list[JSONDict] = []
    semantic_part_count = 0
    for index, value in enumerate(content_value):
        part = require_content_part_dict(
            value,
            message=f"Content part at index {index} must be an object.",
        )
        validated_part = _validate_content_part(
            part,
            role=role,
            index=index,
            param_prefix=param_prefix,
        )
        validated_parts.append(validated_part)
        part_type = validated_part.get("type")
        if part_type == "text":
            text = require_content_part_string(
                validated_part.get("text"),
                message="Text content part must include text.",
                allow_empty=True,
            )
            text_parts.append(text)
            if text.strip():
                semantic_part_count += 1
        elif part_type == "soai_path":
            soai_path_parts.append(validated_part)
            semantic_part_count += 1
        elif part_type in {
            "soai_file",
            "soai_file_unavailable",
            "soai_knowledge",
            "soai_knowledge_unavailable",
        }:
            semantic_part_count += 1
        else:
            semantic_part_count += 1
    if semantic_part_count == 0:
        raise ValidationError("Message content must be semantically non-empty.")
    if soai_path_parts:
        if len(text_parts) > 1:
            raise ValidationError(
                "Messages with SoAI path records must contain at most one text part.",
            )
        validate_no_raw_soai_path_tokens(validated_parts)
    else:
        validate_no_raw_soai_path_tokens(validated_parts)
    return validated_parts
