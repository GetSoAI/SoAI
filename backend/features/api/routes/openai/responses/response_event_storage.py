"""SoAI - Canonical OpenAI Responses event storage writes [backend/features/api/routes/openai/responses/response_event_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.openai.response_event_normalization import (
    normalize_responses_event_for_storage,
)
from core.openai.responses_events import coerce_response_created_at
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "ResponseStorageTarget",
    "StoredResponseEvent",
    "normalize_stored_response_event",
    "persist_normalized_response_event",
)


@dataclass(frozen=True, slots=True)
class ResponseStorageTarget:
    response_id: str
    task_id: str
    user_id: int | None
    api_key_id: str | None
    model: str
    created_at: int
    is_background: bool
    stream_enabled: bool


@dataclass(frozen=True, slots=True)
class StoredResponseEvent:
    event_payload: JSONDict
    response_json: JSONDict
    status: str
    terminal: bool
    response_id: str
    model: str
    created_at: int


def normalize_stored_response_event(
    *,
    target: ResponseStorageTarget,
    payload: JSONDict,
    sequence_number: int,
    default_status: str,
) -> StoredResponseEvent:
    normalized_payload, response_json, status, terminal = normalize_responses_event_for_storage(
        payload=payload,
        response_id=target.response_id,
        sequence_number=sequence_number,
        default_status=default_status,
        model=target.model,
        created_at=target.created_at,
    )
    response_created_at = coerce_response_created_at(
        response_json.get("created_at"),
        default=target.created_at,
    )
    model_value = response_json.get("model")
    response_model = model_value if isinstance(model_value, str) and model_value else target.model
    response_id_value = response_json.get("id")
    response_id = (
        response_id_value
        if isinstance(response_id_value, str) and response_id_value
        else target.response_id
    )
    return StoredResponseEvent(
        event_payload=normalized_payload,
        response_json=response_json,
        status=status,
        terminal=terminal,
        response_id=response_id,
        model=response_model,
        created_at=response_created_at,
    )


async def persist_normalized_response_event(
    *,
    api_context: ApiContext,
    target: ResponseStorageTarget,
    stored_event: StoredResponseEvent,
    sequence_number: int,
    input_items: tuple[JSONDict, ...] | None = None,
    reset_events: bool = False,
    event_created_at_ms: int | None = None,
) -> None:
    now_ms = int(epoch_ms() if event_created_at_ms is None else event_created_at_ms)
    persisted = await api_context.dependencies.database_openai_responses.upsert_response_artifacts(
        response_id=stored_event.response_id,
        task_id=target.task_id,
        user_id=target.user_id,
        api_key_id=target.api_key_id,
        model=stored_event.model,
        created_at_seconds=stored_event.created_at,
        status=stored_event.status,
        store=True,
        is_background=target.is_background,
        stream_enabled=target.stream_enabled,
        response_json=stored_event.response_json,
        input_items=input_items,
        input_items_created_at_ms=now_ms,
        event_payloads=(stored_event.event_payload,),
        event_sequence_start=sequence_number,
        reset_events=reset_events,
        create_if_missing=True,
        event_created_at_ms=now_ms,
    )
    if not persisted:
        raise StateError("Initial Response persistence was rejected.")
