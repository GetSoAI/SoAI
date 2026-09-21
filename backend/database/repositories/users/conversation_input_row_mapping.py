"""SoAI - Conversation input row mapping [backend/database/repositories/users/conversation_input_row_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.types.json import is_json_dict, is_json_list
from core.validation.attachment_content import require_attachment_content_list
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from database.core.json_codec import safe_json_deserialize
from database.repositories.users.conversation_input_constants import VALID_INPUT_STATES

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = ("format_conversation_input_row",)


def _require_input_type(value: SQLiteValue) -> str:
    normalized_value = coerce_optional_trimmed_str(value)
    if normalized_value is None:
        raise StateError("Conversation input row is missing input_type.")
    normalized = normalized_value.lower()
    if normalized not in {"prompt", "steer", "control"}:
        raise StateError("Conversation input row has invalid input_type.")
    return normalized


def _require_transport_origin(value: SQLiteValue) -> str:
    normalized_value = coerce_optional_trimmed_str(value)
    if normalized_value not in {"chat", "messaging"}:
        raise StateError("Conversation input row has invalid transport_origin.")
    return normalized_value


def _require_attachment_content(value: SQLiteValue) -> list[JSONDict]:
    if not isinstance(value, str) or not value:
        raise StateError("Conversation input row is missing attachment_content_json.")
    array_message = "Conversation input row attachment_content_json must be a JSON array."
    try:
        decoded = safe_json_deserialize(value)
    except ValidationError as exception:
        raise StateError(
            "Conversation input row attachment_content_json is invalid JSON.",
        ) from exception
    if not is_json_list(decoded):
        raise StateError(array_message)
    return require_attachment_content_list(
        decoded,
        build_error=StateError,
        invalid_message=array_message,
        entry_object_message="Conversation input attachment_content entries must be JSON objects.",
        entry_type_message=(
            "Conversation input attachment_content entries must include a non-empty type."
        ),
    )


def _decode_json_object(value: SQLiteValue, *, field: str, nullable: bool) -> JSONDict | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise StateError(f"Conversation input row is missing {field}.")
    try:
        decoded = safe_json_deserialize(value)
    except ValidationError as exception:
        raise StateError(f"Conversation input row {field} is invalid JSON.") from exception
    if not is_json_dict(decoded):
        raise StateError(f"Conversation input row {field} must be a JSON object.")
    return decoded


def _decode_json_array(value: SQLiteValue, *, field: str) -> list[JSONDict]:
    if not isinstance(value, str) or not value:
        raise StateError(f"Conversation input row is missing {field}.")
    try:
        decoded = safe_json_deserialize(value)
    except ValidationError as exception:
        raise StateError(f"Conversation input row {field} is invalid JSON.") from exception
    if not is_json_list(decoded) or not all(is_json_dict(entry) for entry in decoded):
        raise StateError(f"Conversation input row {field} must be an array of objects.")
    normalized: list[JSONDict] = []
    for entry in decoded:
        if not is_json_dict(entry):
            raise StateError(f"Conversation input row {field} must be an array of objects.")
        normalized.append(entry)
    return normalized


def _require_non_negative_int(row: SQLiteRowDict, field: str) -> int:
    value = row.get(field)
    if not is_strict_int(value) or value < 0:
        raise StateError(f"Conversation input row has invalid {field}.")
    return int(value)


def format_conversation_input_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if row is None:
        return None
    input_id = coerce_optional_trimmed_str(row.get("input_id"))
    if input_id is None:
        raise StateError("Conversation input row is missing input_id.")
    input_type = _require_input_type(row.get("input_type"))
    transport_origin = _require_transport_origin(row.get("transport_origin"))
    text_value = row.get("text")
    if not isinstance(text_value, str):
        raise StateError("Conversation input row is missing text.")
    text = text_value
    attachment_content = _require_attachment_content(row.get("attachment_content_json"))
    state = coerce_optional_trimmed_str(row.get("state"))
    if state is None or state not in VALID_INPUT_STATES:
        raise StateError("Conversation input row is missing state.")
    accepted_at_value = row.get("accepted_at_ms")
    try:
        accepted_at_ms = require_unix_epoch_ms(
            accepted_at_value,
            error_message="Conversation input row is missing accepted_at_ms.",
            enforce_maximum=False,
        )
    except ValidationError as exception:
        raise StateError("Conversation input row is missing accepted_at_ms.") from exception
    model_settings = _decode_json_object(
        row.get("model_settings_json"),
        field="model_settings_json",
        nullable=input_type != "prompt",
    )
    source_metadata = _decode_json_object(
        row.get("source_metadata_json"),
        field="source_metadata_json",
        nullable=False,
    )
    if source_metadata is None:
        raise StateError("Conversation input row source_metadata_json is missing.")
    media_descriptors = _decode_json_array(
        row.get("media_descriptors_json"),
        field="media_descriptors_json",
    )
    regeneration_request = _decode_json_object(
        row.get("regeneration_request_json"),
        field="regeneration_request_json",
        nullable=True,
    )
    if (
        input_type != "control"
        and not text.strip()
        and not attachment_content
        and not media_descriptors
        and regeneration_request is None
    ):
        raise StateError("Conversation input row is missing text and attachments.")
    return {
        "input_id": input_id,
        "conv_id": row.get("conv_id"),
        "user_id": row.get("user_id"),
        "input_type": input_type,
        "transport_origin": transport_origin,
        "text": text,
        "attachment_content": attachment_content,
        "model_settings": model_settings,
        "source_key": row.get("source_key"),
        "content_fingerprint": row.get("content_fingerprint"),
        "source_metadata": source_metadata,
        "media_descriptors": media_descriptors,
        "regeneration_request": regeneration_request,
        "regeneration_accepted_revision": row.get("regeneration_accepted_revision"),
        "state": state,
        "accepted_at_ms": accepted_at_ms,
        "conversation_generation": _require_non_negative_int(row, "conversation_generation"),
        "claim_generation": _require_non_negative_int(row, "claim_generation"),
        "client_id": row.get("client_id"),
        "client_request_id": row.get("client_request_id"),
        "messaging_ingress_id": row.get("messaging_ingress_id"),
        "claim_owner": row.get("claim_owner"),
        "claim_server_boot_id": row.get("claim_server_boot_id"),
        "target_input_id": row.get("target_input_id"),
        "materialized_message_id": row.get("materialized_message_id"),
        "materialized_message_at_ms": row.get("materialized_message_at_ms"),
        "request_id": row.get("request_id"),
        "assistant_at_ms": row.get("assistant_at_ms"),
        "assistant_turn_at_ms": row.get("assistant_turn_at_ms"),
        "model_variant_index": row.get("model_variant_index"),
        "agent_turn_id": row.get("agent_turn_id"),
        "task_id": row.get("task_id"),
        "suspension_phase": row.get("suspension_phase"),
        "suspension_iteration": row.get("suspension_iteration"),
        "suspension_tool_call_id": row.get("suspension_tool_call_id"),
        "suspension_generation": row.get("suspension_generation"),
        "terminal_code": row.get("terminal_code"),
        "terminal_args": _decode_json_object(
            row.get("terminal_args_json"),
            field="terminal_args_json",
            nullable=True,
        ),
        "claimed_at_ms": row.get("claimed_at_ms"),
        "materialized_at_ms": row.get("materialized_at_ms"),
        "running_at_ms": row.get("running_at_ms"),
        "input_required_at_ms": row.get("input_required_at_ms"),
        "terminal_at_ms": row.get("terminal_at_ms"),
        "updated_at_ms": row.get("updated_at_ms"),
    }
