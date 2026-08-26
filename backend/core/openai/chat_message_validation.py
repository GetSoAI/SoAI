"""SoAI - OpenAI chat message validation [backend/core/openai/chat_message_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.openai.chat_messages_contracts import extract_expected_tool_call_ids
from core.openai.chat_role_sets import OPENAI_ALLOWED_ROLES
from core.openai.message_content_validation import validate_message_content_json
from core.types.json import JSONDict, JSONValue
from core.validation.strings import coerce_trimmed_str_or_empty

__all__ = ("validate_chat_message_dict",)


def _allowed_content_part_types_for_role(role: str) -> frozenset[str]:
    if role in ("system", "developer", "tool"):
        return frozenset(("text",))
    if role == "assistant":
        return frozenset(("text", "refusal"))
    if role == "user":
        return frozenset(("text", "image_url", "input_audio", "file"))
    return frozenset()


def _coerce_role(value: JSONValue) -> str:
    return coerce_trimmed_str_or_empty(value)


def _require_non_empty_text(
    value: JSONValue,
    *,
    message_index: int,
    field: str,
    allow_empty: bool,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"{field} must be a string.",
            details={"param": f"messages[{message_index}].{field}"},
        )
    if allow_empty:
        return value
    if not value.strip():
        raise ValidationError(
            f"{field} must be a non-empty string.",
            details={"param": f"messages[{message_index}].{field}"},
        )
    return value


def _validate_tool_message_fields(message: JSONDict, *, message_index: int) -> None:
    tool_call_id = coerce_trimmed_str_or_empty(message.get("tool_call_id"))
    if not tool_call_id:
        raise ValidationError(
            "tool_call_id is required for tool messages.",
            details={"param": f"messages[{message_index}].tool_call_id"},
        )


def _validate_tool_calls_shape(message: JSONDict, *, message_index: int) -> None:
    tool_calls_value = message.get("tool_calls")
    if tool_calls_value is None:
        return
    if not isinstance(tool_calls_value, list):
        raise ValidationError(
            "tool_calls must be an array.",
            details={"param": f"messages[{message_index}].tool_calls"},
        )
    if tool_calls_value:
        extract_expected_tool_call_ids(tool_calls_value, message_index=message_index)


def _validate_content_parts_allowed_types(
    validated_parts: list[JSONDict],
    *,
    role: str,
    param_prefix: str,
) -> None:
    allowed_types = _allowed_content_part_types_for_role(role)
    observed_types: list[str] = []
    for part_index, part in enumerate(validated_parts):
        part_type = coerce_trimmed_str_or_empty(part.get("type"))
        observed_types.append(part_type)
        if part_type not in allowed_types:
            raise ValidationError(
                "Content part type is not allowed for this role.",
                details={
                    "param": f"{param_prefix}[{part_index}].type",
                    "role": role,
                    "type": part_type,
                    "allowed": sorted(allowed_types),
                },
            )
    if role == "assistant" and "refusal" in observed_types:
        if len(observed_types) != 1 or observed_types[0] != "refusal":
            raise ValidationError(
                "Assistant refusal content must be provided as a single refusal part.",
                details={"param": param_prefix},
            )


def validate_chat_message_dict(message: JSONDict, *, message_index: int) -> None:
    role_value = message.get("role")
    role = _coerce_role(role_value)
    if role not in OPENAI_ALLOWED_ROLES:
        raise ValidationError(
            f"Unsupported role '{role_value}'.",
            details={"param": f"messages[{message_index}].role"},
        )
    function_call_value = message.get("function_call")
    if role != "assistant" and function_call_value is not None:
        raise ValidationError(
            "function_call is only allowed for assistant messages.",
            details={"param": f"messages[{message_index}].function_call"},
        )
    tool_calls_value = message.get("tool_calls")
    if role != "assistant" and tool_calls_value is not None:
        raise ValidationError(
            "tool_calls are only allowed for assistant messages.",
            details={"param": f"messages[{message_index}].tool_calls"},
        )
    if role == "tool":
        _validate_tool_message_fields(message, message_index=message_index)
    if role == "assistant":
        _validate_tool_calls_shape(message, message_index=message_index)
    if role == "function":
        name_value = message.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            raise ValidationError(
                "Function messages require a non-empty name.",
                details={"param": f"messages[{message_index}].name"},
            )

    if "content" not in message:
        if role == "assistant":
            return
        raise ValidationError(
            "content is required.",
            details={"param": f"messages[{message_index}].content"},
        )
    content_value = message.get("content")
    if content_value is None:
        if role == "assistant":
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                return
            if isinstance(function_call_value, dict) and function_call_value:
                return
            raise ValidationError(
                "Assistant messages must include content unless tool_calls or function_call are provided.",
                details={"param": f"messages[{message_index}].content"},
            )
        if role == "function":
            return
        raise ValidationError(
            "content must be a string or array of content parts.",
            details={"param": f"messages[{message_index}].content"},
        )
    if isinstance(content_value, str):
        allow_empty = role in {"assistant", "tool", "function"}
        _require_non_empty_text(
            content_value,
            message_index=message_index,
            field="content",
            allow_empty=allow_empty,
        )
        return
    if isinstance(content_value, list):
        validated = validate_message_content_json(
            content_value,
            param_prefix=f"messages[{message_index}].content",
        )
        if not isinstance(validated, list):
            raise ValidationError(
                "Message content must be an array.",
                details={"param": f"messages[{message_index}].content"},
            )
        _validate_content_parts_allowed_types(
            validated,
            role=role,
            param_prefix=f"messages[{message_index}].content",
        )
        return
    raise ValidationError(
        "content must be a string or array of content parts.",
        details={"param": f"messages[{message_index}].content"},
    )
