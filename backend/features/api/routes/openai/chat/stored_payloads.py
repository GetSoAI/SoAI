"""SoAI - Stored chat completion payload normalization [backend/features/api/routes/openai/chat/stored_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.timing.durations import ms_to_seconds_floor
from core.timing.epoch import epoch_seconds
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "build_deleted_chat_completion_payload",
    "build_stored_chat_completion_record_payload",
    "prepare_stored_chat_completion_payload",
)

CHAT_COMPLETION_OBJECT = "chat.completion"
CHAT_COMPLETION_DELETED_OBJECT = "chat.completion.deleted"


@dataclass(frozen=True, slots=True)
class PreparedStoredChatCompletionPayload:
    completion_id: str
    model: str
    created_at_seconds: int
    metadata_json: JSONDict
    completion_json: JSONDict


def _read_trimmed_str(payload: JSONDict, key: str) -> str | None:
    return coerce_optional_trimmed_str(payload.get(key))


def _resolve_metadata(request_json: JSONDict) -> JSONDict:
    metadata_value = request_json.get("metadata")
    return dict(metadata_value) if isinstance(metadata_value, dict) else {}


def _resolve_created_at_seconds(completion_json: JSONDict) -> int:
    created_value = completion_json.get("created")
    if is_strict_int(created_value):
        return int(created_value)
    return int(epoch_seconds())


def _resolve_record_created_at_seconds(record: JSONDict) -> int | None:
    created_at_ms = record.get("created_at_ms")
    if is_strict_int(created_at_ms):
        return ms_to_seconds_floor(created_at_ms)
    return None


def prepare_stored_chat_completion_payload(
    *,
    completion_json: JSONDict,
    request_json: JSONDict,
) -> PreparedStoredChatCompletionPayload | None:
    completion_id = _read_trimmed_str(completion_json, "id")
    if completion_id is None:
        return None
    model = _read_trimmed_str(completion_json, "model") or _read_trimmed_str(
        request_json,
        "model",
    )
    if model is None:
        return None
    metadata_json = _resolve_metadata(request_json)
    created_at_seconds = _resolve_created_at_seconds(completion_json)
    normalized_completion_json: JSONDict = dict(completion_json)
    normalized_completion_json["id"] = completion_id
    normalized_completion_json["object"] = CHAT_COMPLETION_OBJECT
    normalized_completion_json["model"] = model
    normalized_completion_json["created"] = created_at_seconds
    normalized_completion_json["metadata"] = dict(metadata_json)
    return PreparedStoredChatCompletionPayload(
        completion_id=completion_id,
        model=model,
        created_at_seconds=created_at_seconds,
        metadata_json=metadata_json,
        completion_json=normalized_completion_json,
    )


def _build_stored_chat_completion_response_payload(
    *,
    completion_json: JSONDict,
    metadata_json: JSONDict | None,
    fallback_completion_id: str | None,
    fallback_model: str | None,
    fallback_created_at_seconds: int | None,
) -> JSONDict:
    normalized: JSONDict = dict(completion_json)
    metadata_payload = metadata_json if isinstance(metadata_json, dict) else {}
    normalized["object"] = CHAT_COMPLETION_OBJECT
    normalized["metadata"] = dict(metadata_payload)
    completion_id = _read_trimmed_str(normalized, "id") or coerce_optional_trimmed_str(
        fallback_completion_id,
    )
    if completion_id is not None:
        normalized["id"] = completion_id
    model = _read_trimmed_str(normalized, "model") or fallback_model
    if model is not None:
        normalized["model"] = model
    created_value = normalized.get("created")
    if isinstance(fallback_created_at_seconds, int) and not isinstance(
        fallback_created_at_seconds,
        bool,
    ):
        normalized["created"] = int(fallback_created_at_seconds)
    elif not is_strict_int(created_value):
        normalized.pop("created", None)
    return normalized


def build_stored_chat_completion_record_payload(
    record: JSONDict,
    *,
    fallback_completion_id: str | None,
) -> JSONDict | None:
    completion_json_value = record.get("completion_json")
    if not isinstance(completion_json_value, dict):
        return None
    metadata_json_value = record.get("metadata_json")
    metadata_json: JSONDict = (
        dict(metadata_json_value) if isinstance(metadata_json_value, dict) else {}
    )
    return _build_stored_chat_completion_response_payload(
        completion_json=dict(completion_json_value),
        metadata_json=metadata_json,
        fallback_completion_id=fallback_completion_id,
        fallback_model=_read_trimmed_str(record, "model"),
        fallback_created_at_seconds=_resolve_record_created_at_seconds(record),
    )


def build_deleted_chat_completion_payload(completion_id: str) -> JSONDict:
    return {
        "object": CHAT_COMPLETION_DELETED_OBJECT,
        "id": completion_id,
        "deleted": True,
    }
