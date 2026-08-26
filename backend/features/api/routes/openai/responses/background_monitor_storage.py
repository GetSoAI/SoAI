"""SoAI - OpenAI Responses background monitor persistence [backend/features/api/routes/openai/responses/background_monitor_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from features.api.routes.openai.responses.background_monitor_state import (
    BackgroundResponsesState,
)
from features.api.routes.openai.responses.response_event_storage import (
    ResponseStorageTarget,
    normalize_stored_response_event,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("append_response_event",)


async def append_response_event(
    api_context: ApiContext,
    state: BackgroundResponsesState,
    *,
    payload: JSONDict,
) -> bool:
    stored_event = normalize_stored_response_event(
        target=ResponseStorageTarget(
            response_id=state.response_id,
            task_id=state.task_id,
            user_id=state.user_id,
            api_key_id=state.api_key_id,
            model=state.model,
            created_at=state.created_at,
            is_background=True,
            stream_enabled=state.stream_enabled,
        ),
        payload=payload,
        sequence_number=0,
        default_status="in_progress",
    )
    if stored_event.terminal:
        return True
    sequence = (
        await api_context.dependencies.database_openai_responses.append_nonterminal_response_event(
            response_id=state.response_id,
            response_json=stored_event.response_json,
            event_json=stored_event.event_payload,
            event_created_at_ms=int(epoch_ms()),
            user_id=state.user_id,
            api_key_id=state.api_key_id,
        )
    )
    state.response_id = stored_event.response_id
    state.model = stored_event.model
    state.created_at = stored_event.created_at
    if sequence is None:
        raise StateError("Background Response rejected an ordered nonterminal event.")
    state.event_sequence = sequence + 1
    return False
