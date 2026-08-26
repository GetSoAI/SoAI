"""SoAI - Message row decoding and timeline attachment [backend/database/repositories/users/message_row_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.assistant_timeline.event_timeline_validation import validate_assistant_event_timeline
from core.conversations.assistant_turn_variant_identity import (
    require_assistant_turn_variant_invariants,
)
from core.conversations.conversation_message_type import require_conversation_message_type
from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.validation.coercion import coerce_int
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_json_object
from core.validation.requirements import require_non_negative_int
from database.core.json_codec import safe_json_deserialize
from database.core.row_fields import coerce_row_optional_non_negative_int
from database.repositories.users.assistant_event_field_validation import (
    validate_assistant_event_assistant_revision,
    validate_assistant_event_epoch_timestamp,
    validate_assistant_event_sequence,
    validate_assistant_event_type,
)
from database.repositories.users.message_compaction_markers import attach_context_compaction_markers
from database.repositories.users.message_metrics import calculate_generation_speed_tokens_per_sec
from database.repositories.users.message_usage_fields import read_message_usage_fields

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "attach_assistant_event_timeline",
    "build_message_payload_from_row",
)


def build_message_payload_from_row(row: SQLiteRow) -> JSONDict:
    role = row["role"]
    if not isinstance(role, str):
        raise ValidationError("Conversation message role must be a string.")
    content_raw = safe_json_deserialize(row.get("content"), "")
    content_value: str | list[JSONDict]
    if isinstance(content_raw, str):
        content_value = content_raw
    elif isinstance(content_raw, list):
        content_parts: list[JSONDict] = []
        for part in content_raw:
            content_parts.append(
                require_json_object(
                    normalize_for_json(part),
                    label="Conversation message content part",
                    build_error=ValidationError,
                    invalid_message="Conversation message content part must be an object.",
                ),
            )
        content_value = content_parts
    elif content_raw is None:
        content_value = ""
    else:
        raise ValidationError("Conversation message content must be a string or array.")

    created_at_ms_value = require_unix_epoch_ms(
        row["created_at_ms"],
        error_message="Conversation message created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    message_data: JSONDict = {
        "role": role,
        "message_type": require_conversation_message_type(
            (row.get("message_type") if isinstance(row.get("message_type"), str) else None),
        ),
        "content": content_value,
        "timestamp": created_at_ms_value,
    }
    conversation_input_id = row.get("conversation_input_id")
    if conversation_input_id is not None:
        if not isinstance(conversation_input_id, str) or not conversation_input_id.strip():
            raise ValidationError(
                "Conversation message conversation_input_id must be a non-empty string."
            )
        message_data["conversation_input_id"] = conversation_input_id
    messaging_sender_display_name = row.get("messaging_sender_display_name")
    if messaging_sender_display_name is not None:
        if (
            not isinstance(messaging_sender_display_name, str)
            or not messaging_sender_display_name.strip()
        ):
            raise ValidationError(
                "Conversation message messaging sender display name must be a non-empty string.",
            )
        message_data["messaging_sender_display_name"] = messaging_sender_display_name.strip()
    messaging_sender_id = row.get("messaging_sender_id")
    if messaging_sender_id is not None:
        if not isinstance(messaging_sender_id, str) or not messaging_sender_id.strip():
            raise ValidationError(
                "Conversation message messaging sender id must be a non-empty string.",
            )
        message_data["messaging_sender_id"] = messaging_sender_id.strip()

    assistant_turn_at_ms_value = row.get("assistant_turn_at_ms")
    assistant_turn_at_ms: int | None = None
    if assistant_turn_at_ms_value is not None:
        assistant_turn_at_ms = require_unix_epoch_ms(
            assistant_turn_at_ms_value,
            error_message="Conversation message assistant_turn_at_ms must be an epoch-millisecond integer when provided.",
            enforce_maximum=False,
        )
        message_data["assistant_turn_at_ms"] = assistant_turn_at_ms

    model_variant_index_value = row.get("model_variant_index")
    model_variant_index: int | None = None
    if model_variant_index_value is not None:
        model_variant_index = require_non_negative_int(
            model_variant_index_value,
            error_message="Conversation message model_variant_index must be a non-negative integer when provided.",
        )
        message_data["model_variant_index"] = model_variant_index

    if role == "assistant":
        if assistant_turn_at_ms is None or model_variant_index is None:
            raise ValidationError(
                "Assistant conversation messages must define assistant_turn_at_ms and model_variant_index.",
            )
        require_assistant_turn_variant_invariants(
            assistant_at_ms=created_at_ms_value,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            assistant_turn_after_assistant_error_message=(
                "Assistant conversation message assistant_turn_at_ms must not be greater than timestamp."
            ),
            canonical_variant_mismatch_error_message=(
                "Canonical assistant conversation messages must have timestamp equal to assistant_turn_at_ms."
            ),
        )

    message_id_value = row.get("id")
    if message_id_value is not None:
        if (
            isinstance(message_id_value, bool)
            or not isinstance(message_id_value, int)
            or message_id_value < 0
        ):
            raise ValidationError("Conversation message id must be a non-negative integer.")
        message_data["id"] = message_id_value

    model_id_value = row.get("model_id")
    if model_id_value is not None:
        message_data["model_id"] = str(model_id_value)

    usage_fields = read_message_usage_fields(row, role=role)
    message_data.update(usage_fields.payload)

    generation_latency_value = row.get("generation_latency_ms")
    if generation_latency_value is not None:
        if isinstance(generation_latency_value, bool) or not isinstance(
            generation_latency_value,
            int,
        ):
            raise ValidationError("Conversation message generation_latency_ms must be an integer.")
        message_data["generation_latency_ms"] = generation_latency_value

    finish_reason_value = row.get("finish_reason")
    if finish_reason_value is not None:
        message_data["finish_reason"] = str(finish_reason_value)

    thinking_tail_duration_ms = coerce_row_optional_non_negative_int(
        row.get("thinking_tail_duration_ms"),
    )
    if thinking_tail_duration_ms is not None:
        message_data["thinking_tail_duration_ms"] = thinking_tail_duration_ms

    completion_tokens = usage_fields.completion_tokens
    generation_latency_ms = coerce_int(generation_latency_value)
    generation_speed = calculate_generation_speed_tokens_per_sec(
        completion_tokens,
        generation_latency_ms,
    )
    if generation_speed is not None:
        message_data["generation_speed_tokens_per_sec"] = generation_speed
    return message_data


@dataclass(frozen=True, slots=True)
class _AssistantTimelineEvent:
    sequence: int
    assistant_revision: int
    event_type: str
    payload: JSONDict

    def as_json_dict(self) -> JSONDict:
        return {
            "sequence": self.sequence,
            "assistant_revision": self.assistant_revision,
            "event_type": self.event_type,
            "payload": self.payload,
        }


def attach_assistant_event_timeline(
    messages: list[JSONDict],
    assistant_events: Sequence[SQLiteRow],
) -> None:
    events_by_timestamp: dict[int, list[_AssistantTimelineEvent]] = {}
    for event_row in assistant_events:
        assistant_at_ms = event_row.get("assistant_at_ms")
        sequence = event_row.get("sequence")
        assistant_revision = event_row.get("assistant_revision")
        event_type = event_row.get("event_type")
        payload_raw = event_row.get("payload_json")
        validated_timestamp = validate_assistant_event_epoch_timestamp(
            assistant_at_ms,
            field_name="assistant_at_ms",
        )
        validated_sequence = validate_assistant_event_sequence(sequence)
        validated_assistant_revision = validate_assistant_event_assistant_revision(
            assistant_revision,
        )
        validated_event_type = validate_assistant_event_type(event_type)
        payload = require_json_object(
            normalize_for_json(safe_json_deserialize(payload_raw, None)),
            label="Assistant event payload_json",
            build_error=ValidationError,
            invalid_message="Assistant event payload_json must decode to a JSON object.",
        )
        event_payload = _AssistantTimelineEvent(
            sequence=validated_sequence,
            assistant_revision=validated_assistant_revision,
            event_type=validated_event_type,
            payload=payload,
        )
        if validated_timestamp not in events_by_timestamp:
            events_by_timestamp[validated_timestamp] = []
        events_by_timestamp[validated_timestamp].append(event_payload)

    for per_timestamp_events in events_by_timestamp.values():
        per_timestamp_events.sort(key=lambda item: (item.sequence, item.assistant_revision))

    for message_index, message in enumerate(messages):
        role = message.get("role")
        timestamp = message.get("timestamp")
        if role != "assistant":
            continue
        if not is_strict_int(timestamp):
            raise ValidationError(
                "Assistant message timestamp must be an integer when attaching event timeline.",
            )
        timeline_events = events_by_timestamp.get(timestamp)
        if timeline_events is None:
            message["assistant_event_timeline"] = []
            validate_assistant_event_timeline(
                message.get("assistant_event_timeline"),
                message_index=message_index,
                assistant_at_ms=timestamp,
            )
            continue
        message["assistant_event_timeline"] = [
            event_item.as_json_dict() for event_item in timeline_events
        ]
        validate_assistant_event_timeline(
            message.get("assistant_event_timeline"),
            message_index=message_index,
            assistant_at_ms=timestamp,
        )

    attach_context_compaction_markers(messages)
