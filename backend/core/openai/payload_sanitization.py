"""SoAI - OpenAI message payload sanitization [backend/core/openai/payload_sanitization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.message_fields import OPENAI_MESSAGE_FIELDS_REQUEST
from core.openai.message_payload_access import get_openai_payload_message_dicts
from core.openai.request_field_validation import select_first_field_name

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "sanitize_openai_request_messages",
    "sanitize_openai_tool_call_payload",
)


def sanitize_openai_tool_call_payload(
    call: JSONDict,
    *,
    message_index: int,
    call_index: int,
    logger: LoggerProtocol | None,
    trace_id: str | None,
) -> JSONDict:
    extra_call_keys = [key for key in call if key not in {"id", "type", "function"}]
    if extra_call_keys:
        field = select_first_field_name(list(extra_call_keys))
        raise ValidationError(
            f"Unsupported field: '{field}'.",
            details={"param": f"messages[{message_index}].tool_calls[{call_index}].{field}"},
            trace_id=trace_id,
        )
    call_id = call.get("id")
    if call_id is not None and not isinstance(call_id, str):
        raise ValidationError(
            f"Message at index {message_index} tool_calls[{call_index}].id must be a string.",
            details={"param": f"messages[{message_index}].tool_calls[{call_index}].id"},
            trace_id=trace_id,
        )
    call_type = call.get("type")
    if not isinstance(call_type, str) or not call_type.strip():
        if logger is not None:
            logger.debug(
                "[%s] OpenAI request violation: tool_calls[%s].type missing or invalid.",
                trace_id or "unknown",
                call_index,
            )
        raise ValidationError(
            f"Message at index {message_index} tool_calls[{call_index}].type must be a non-empty string.",
            details={"param": f"messages[{message_index}].tool_calls[{call_index}].type"},
            trace_id=trace_id,
        )
    function_payload_value = call.get("function")
    if not isinstance(function_payload_value, dict):
        if logger is not None:
            logger.debug(
                "[%s] OpenAI request violation: tool_calls[%s].function missing or invalid.",
                trace_id or "unknown",
                call_index,
            )
        raise ValidationError(
            f"Message at index {message_index} tool_calls[{call_index}].function must be an object.",
            details={"param": f"messages[{message_index}].tool_calls[{call_index}].function"},
            trace_id=trace_id,
        )
    extra_function_keys = [
        key for key in function_payload_value if key not in {"name", "arguments"}
    ]
    if extra_function_keys:
        field = select_first_field_name(list(extra_function_keys))
        raise ValidationError(
            f"Unsupported field: '{field}'.",
            details={
                "param": f"messages[{message_index}].tool_calls[{call_index}].function.{field}",
            },
            trace_id=trace_id,
        )
    name_value = function_payload_value.get("name")
    arguments_value = function_payload_value.get("arguments")
    if not isinstance(name_value, str) or not name_value.strip():
        if logger is not None:
            logger.debug(
                "[%s] OpenAI request violation: tool_calls[%s].function.name missing or invalid.",
                trace_id or "unknown",
                call_index,
            )
        raise ValidationError(
            f"Message at index {message_index} tool_calls[{call_index}].function.name must be a non-empty string.",
            details={"param": f"messages[{message_index}].tool_calls[{call_index}].function.name"},
            trace_id=trace_id,
        )
    if arguments_value is not None and not isinstance(arguments_value, str):
        if logger is not None:
            logger.debug(
                "[%s] OpenAI request violation: tool_calls[%s].function.arguments not a string.",
                trace_id or "unknown",
                call_index,
            )
        raise ValidationError(
            f"Message at index {message_index} tool_calls[{call_index}].function.arguments must be a string.",
            details={
                "param": f"messages[{message_index}].tool_calls[{call_index}].function.arguments",
            },
            trace_id=trace_id,
        )
    normalized_function: JSONDict = {"name": name_value.strip()}
    if arguments_value is not None:
        normalized_function["arguments"] = arguments_value
    normalized_call: JSONDict = {"function": normalized_function}
    if isinstance(call_id, str) and call_id:
        normalized_call["id"] = call_id
    normalized_call["type"] = call_type.strip()
    return normalized_call


def sanitize_openai_request_messages(
    payload: JSONDict,
    *,
    logger: LoggerProtocol | None = None,
    trace_id: str | None = None,
) -> JSONDict:
    messages = get_openai_payload_message_dicts(payload, trace_id=trace_id)
    if messages is None:
        return payload
    sanitized_messages: list[JSONDict] = []
    for index, message in enumerate(messages):
        extra_message_keys = [key for key in message if key not in OPENAI_MESSAGE_FIELDS_REQUEST]
        if extra_message_keys:
            field = select_first_field_name(list(extra_message_keys))
            raise ValidationError(
                f"Unsupported field: '{field}'.",
                details={"param": f"messages[{index}].{field}"},
                trace_id=trace_id,
            )
        sanitized_message: JSONDict = {}
        if "role" in message:
            sanitized_message["role"] = message.get("role")
        if "content" in message:
            sanitized_message["content"] = message.get("content")
        name_value = message.get("name")
        if name_value is not None:
            if not isinstance(name_value, str):
                raise ValidationError(
                    "Message name must be a string.",
                    details={"param": f"messages[{index}].name"},
                    trace_id=trace_id,
                )
            sanitized_message["name"] = name_value
        refusal_value = message.get("refusal")
        if refusal_value is not None:
            if not isinstance(refusal_value, str):
                raise ValidationError(
                    "Message refusal must be a string.",
                    details={"param": f"messages[{index}].refusal"},
                    trace_id=trace_id,
                )
            sanitized_message["refusal"] = refusal_value
        audio_value = message.get("audio")
        if audio_value is not None:
            if not isinstance(audio_value, dict):
                raise ValidationError(
                    "Message audio must be an object.",
                    details={"param": f"messages[{index}].audio"},
                    trace_id=trace_id,
                )
            sanitized_message["audio"] = audio_value
        tool_call_id = message.get("tool_call_id")
        if tool_call_id is not None:
            if not isinstance(tool_call_id, str):
                raise ValidationError(
                    "Message tool_call_id must be a string.",
                    details={"param": f"messages[{index}].tool_call_id"},
                    trace_id=trace_id,
                )
            sanitized_message["tool_call_id"] = tool_call_id
        function_call_value = message.get("function_call")
        if function_call_value is not None:
            if not isinstance(function_call_value, dict):
                raise ValidationError(
                    "Message function_call must be an object.",
                    details={"param": f"messages[{index}].function_call"},
                    trace_id=trace_id,
                )
            extra_function_call_keys = [
                key for key in function_call_value if key not in {"name", "arguments"}
            ]
            if extra_function_call_keys:
                field = select_first_field_name(list(extra_function_call_keys))
                raise ValidationError(
                    f"Unsupported field: '{field}'.",
                    details={"param": f"messages[{index}].function_call.{field}"},
                    trace_id=trace_id,
                )
            function_name_value = function_call_value.get("name")
            if not isinstance(function_name_value, str) or not function_name_value.strip():
                raise ValidationError(
                    "Message function_call.name must be a non-empty string.",
                    details={"param": f"messages[{index}].function_call.name"},
                    trace_id=trace_id,
                )
            function_arguments_value = function_call_value.get("arguments")
            if not isinstance(function_arguments_value, str):
                raise ValidationError(
                    "Message function_call.arguments must be a string.",
                    details={"param": f"messages[{index}].function_call.arguments"},
                    trace_id=trace_id,
                )
            sanitized_message["function_call"] = {
                "name": function_name_value.strip(),
                "arguments": function_arguments_value,
            }
        if "tool_calls" in message:
            tool_calls_value = message.get("tool_calls")
            if tool_calls_value is None or not isinstance(tool_calls_value, list):
                raise ValidationError(
                    f"Message at index {index} tool_calls must be an array.",
                    details={"param": f"messages[{index}].tool_calls"},
                    trace_id=trace_id,
                )
            sanitized_tool_calls: list[JSONDict] = []
            for call_index, call in enumerate(tool_calls_value):
                if not isinstance(call, dict):
                    raise ValidationError(
                        f"Message at index {index} tool_calls[{call_index}] must be an object.",
                        details={"param": f"messages[{index}].tool_calls[{call_index}]"},
                        trace_id=trace_id,
                    )
                sanitized_tool_calls.append(
                    sanitize_openai_tool_call_payload(
                        call,
                        message_index=index,
                        call_index=call_index,
                        logger=logger,
                        trace_id=trace_id,
                    ),
                )
            sanitized_message["tool_calls"] = sanitized_tool_calls
        sanitized_messages.append(sanitized_message)
    payload["messages"] = sanitized_messages
    return payload
