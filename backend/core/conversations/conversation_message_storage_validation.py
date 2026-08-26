"""SoAI - WebUI conversation message storage validation [backend/core/conversations/conversation_message_storage_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.event_timeline_validation import (
    validate_assistant_event_timeline,
)
from core.conversations.assistant_turn_variant_identity import (
    require_assistant_turn_variant_invariants,
)
from core.conversations.assistant_usage_identity import (
    validate_assistant_usage_identity,
)
from core.conversations.conversation_message_role_fields import (
    validate_webui_chat_message_role_fields,
)
from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.conversations.conversation_message_type import (
    require_conversation_message_type,
)
from core.conversations.message_content_validation import (
    validate_webui_message_content_json,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from core.validation.epoch import EPOCH_MS_MIN, require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_optional_non_empty_str
from core.validation.requirements import require_non_negative_int
from core.workspaces.soai_path_text_validation import validate_no_raw_soai_path_tokens

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "validate_message_payload_for_storage",
    "validate_messages_payload_for_storage",
)

_WEBUI_STORAGE_ROLES = frozenset(("system", "developer", "user", "assistant", "tool"))


def _coerce_required_epoch_ms_field(message: JSONDict, field_name: str, index: int) -> int:
    value = message.get(field_name)
    if value is None:
        raise ValidationError(f"Message at index {index} missing required field '{field_name}'.")
    return require_unix_epoch_ms(
        value,
        error_message=(
            f"Message at index {index} field '{field_name}' must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
        ),
        enforce_maximum=False,
    )


def _coerce_optional_int_field(message: JSONDict, field_name: str, index: int) -> int | None:
    value = message.get(field_name)
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(f"Message at index {index} field '{field_name}' must be an integer.")
    return value


def _normalize_assistant_content_for_storage(message: JSONDict) -> None:
    if message.get("role") != "assistant":
        return
    if "content" not in message or message.get("content") is None:
        message["content"] = ""


def _normalize_assistant_event_timeline(message: JSONDict, index: int) -> list[JSONDict]:
    timeline_value = message.get("assistant_event_timeline")
    if not isinstance(timeline_value, list):
        raise ValidationError(
            f"Message at index {index} field 'assistant_event_timeline' must be an array.",
        )
    timeline: list[JSONDict] = []
    for event_index, event_value in enumerate(timeline_value):
        if not isinstance(event_value, dict):
            raise ValidationError(
                f"Message at index {index} assistant_event_timeline[{event_index}] must be an object.",
            )
        normalized_event = normalize_for_json(event_value)
        if not isinstance(normalized_event, dict):
            raise ValidationError(
                f"Message at index {index} assistant_event_timeline[{event_index}] is invalid.",
            )
        timeline.append(dict(normalized_event))
    return timeline


def validate_message_payload_for_storage(
    message: JSONDict,
    index: int,
) -> ConversationMessageStoragePayload:
    if "role" not in message:
        raise ValidationError(f"Message at index {index} missing required field 'role'.")
    role_value = message["role"]
    if not isinstance(role_value, str):
        raise ValidationError(f"Message at index {index} field 'role' must be a string.")
    role = role_value
    if role not in _WEBUI_STORAGE_ROLES:
        raise ValidationError(f"Message at index {index} has unsupported role '{role}'.")
    message_type = require_conversation_message_type(message.get("message_type"))
    if message_type == "control" and role not in {"user", "assistant"}:
        raise ValidationError("Control messages must use the user or assistant role.")
    _normalize_assistant_content_for_storage(message)
    tool_call_id_value = message.get("tool_call_id")
    validate_webui_chat_message_role_fields(
        role=role,
        field_names=frozenset(str(field_name) for field_name in message),
        content_present="content" in message,
        content_is_none=message.get("content") is None,
        assistant_event_timeline_present="assistant_event_timeline" in message,
        assistant_turn_at_ms_present="assistant_turn_at_ms" in message,
        assistant_turn_at_ms_is_none=message.get("assistant_turn_at_ms") is None,
        model_variant_index_present="model_variant_index" in message,
        model_variant_index_is_none=message.get("model_variant_index") is None,
        tool_call_id_present="tool_call_id" in message,
        tool_call_id=tool_call_id_value if isinstance(tool_call_id_value, str) else None,
        tool_calls_present="tool_calls" in message,
        index=index,
    )
    if "content" not in message:
        raise ValidationError(f"Message at index {index} missing required field 'content'.")
    validated_content = validate_webui_message_content_json(
        message["content"],
        role=role,
        param_prefix=f"messages[{index}].content",
    )
    validate_no_raw_soai_path_tokens(validated_content)
    timestamp = _coerce_required_epoch_ms_field(message, "timestamp", index)
    assistant_event_timeline: list[JSONDict] | None
    if role == "assistant":
        if "assistant_event_timeline" not in message:
            raise ValidationError(
                f"Message at index {index} missing required field 'assistant_event_timeline'.",
            )
        validate_assistant_event_timeline(
            message.get("assistant_event_timeline"),
            message_index=index,
            assistant_at_ms=timestamp,
        )
        assistant_event_timeline = _normalize_assistant_event_timeline(message, index)
    else:
        assistant_event_timeline = None
    normalized_tool_call_id: str | None = None
    if role == "tool":
        if not isinstance(tool_call_id_value, str) or not tool_call_id_value.strip():
            raise ValidationError(
                f"Message at index {index} field 'tool_call_id' is required for tool messages.",
            )
        normalized_tool_call_id = tool_call_id_value.strip()
    validated: ConversationMessageStoragePayload = {
        "role": role,
        "message_type": message_type,
        "content_json": serialize_json_compact_stable_strict(validated_content),
        "created_at_ms": timestamp,
    }
    assistant_turn_at_ms = _coerce_optional_int_field(
        message,
        "assistant_turn_at_ms",
        index,
    )
    model_variant_index = _coerce_optional_int_field(message, "model_variant_index", index)
    if role == "assistant":
        if assistant_turn_at_ms is None:
            raise ValidationError(
                f"Message at index {index} field 'assistant_turn_at_ms' is required for assistant messages.",
            )
        require_unix_epoch_ms(
            assistant_turn_at_ms,
            error_message=(
                f"Message at index {index} field 'assistant_turn_at_ms' must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
            ),
            enforce_maximum=False,
        )
        validated["assistant_turn_at_ms"] = assistant_turn_at_ms
        if model_variant_index is None:
            raise ValidationError(
                f"Message at index {index} field 'model_variant_index' is required for assistant messages.",
            )
        validated_model_variant_index = require_non_negative_int(
            model_variant_index,
            error_message=(
                f"Message at index {index} field 'model_variant_index' must be a non-negative integer."
            ),
        )
        require_assistant_turn_variant_invariants(
            assistant_at_ms=timestamp,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=validated_model_variant_index,
            assistant_turn_after_assistant_error_message=(
                f"Message at index {index} field 'assistant_turn_at_ms' must not be greater than timestamp."
            ),
            canonical_variant_mismatch_error_message=(
                f"Message at index {index} canonical assistant message timestamp must equal assistant_turn_at_ms."
            ),
        )
        validated["model_variant_index"] = validated_model_variant_index
        validated["assistant_event_timeline"] = assistant_event_timeline
    elif assistant_turn_at_ms is not None or model_variant_index is not None:
        raise ValidationError(
            f"Message at index {index} comparison fields are only supported for assistant messages.",
        )
    if normalized_tool_call_id is not None:
        validated["tool_call_id"] = normalized_tool_call_id
    model_id_val = message.get("model_id")
    if model_id_val is not None:
        validated["model_id"] = str(model_id_val)
    request_id = require_optional_non_empty_str(
        message.get("request_id"),
        label=f"Message at index {index} field 'request_id'",
        build_error=ValidationError,
        invalid_message=(
            f"Message at index {index} field 'request_id' must be a non-empty string."
        ),
    )
    if request_id is not None:
        validated["request_id"] = request_id
    prompt_tokens = _coerce_optional_int_field(message, "prompt_tokens", index)
    if prompt_tokens is not None:
        validated["prompt_tokens"] = prompt_tokens
    completion_tokens = _coerce_optional_int_field(message, "completion_tokens", index)
    if completion_tokens is not None:
        validated["completion_tokens"] = completion_tokens
    total_tokens = _coerce_optional_int_field(message, "total_tokens", index)
    if total_tokens is not None:
        validated["total_tokens"] = total_tokens
    usage_source = require_optional_non_empty_str(
        message.get("usage_source"),
        label=f"Message at index {index} field 'usage_source'",
        build_error=ValidationError,
        invalid_message=(
            f"Message at index {index} field 'usage_source' must be a non-empty string."
        ),
    )
    if usage_source is not None:
        validated["usage_source"] = usage_source
    validate_assistant_usage_identity(
        role=role,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_id=request_id,
        usage_source=usage_source,
        context_label=f"Message at index {index}",
    )
    generation_latency_ms = _coerce_optional_int_field(message, "generation_latency_ms", index)
    if generation_latency_ms is not None:
        validated["generation_latency_ms"] = generation_latency_ms
    finish_reason_val = message.get("finish_reason")
    if finish_reason_val is not None:
        validated["finish_reason"] = str(finish_reason_val)
    thinking_tail_duration_ms = _coerce_optional_int_field(
        message,
        "thinking_tail_duration_ms",
        index,
    )
    if thinking_tail_duration_ms is not None:
        if thinking_tail_duration_ms < 0:
            raise ValidationError(
                f"Message at index {index} field 'thinking_tail_duration_ms' must be a non-negative integer.",
            )
        validated["thinking_tail_duration_ms"] = thinking_tail_duration_ms
    return validated


def validate_messages_payload_for_storage(
    messages: list[JSONDict],
) -> list[ConversationMessageStoragePayload]:
    validated: list[ConversationMessageStoragePayload] = []
    previous_timestamp: int | None = None
    for index, message in enumerate(messages or []):
        validated_message = validate_message_payload_for_storage(message, index)
        timestamp_value = validated_message["created_at_ms"]
        if not isinstance(timestamp_value, int):
            raise ValidationError(
                f"Message at index {index} field 'created_at_ms' must be an epoch-millisecond integer >= {EPOCH_MS_MIN}.",
            )
        if previous_timestamp is not None and timestamp_value <= previous_timestamp:
            raise ValidationError(
                "Message timestamps must be strictly increasing to preserve chronological ordering.",
            )
        previous_timestamp = timestamp_value
        validated.append(validated_message)
    return validated
