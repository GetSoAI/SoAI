"""SoAI - OpenAI Responses passthrough metadata setup [backend/features/api/routes/openai/responses/passthrough_response_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from core.openai.request_options import extract_openai_store_flag
from core.openai.responses_provider_state import (
    ResponsesProviderState,
)
from core.timing.durations import ms_to_seconds_floor
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.api.routes.openai.responses.response_event_storage import (
    ResponseStorageTarget,
)
from features.api.routes.openai.storage_owner import resolve_responses_storage_owner

__all__ = (
    "ResponsesPassthroughResponseSetup",
    "prepare_responses_passthrough_response_setup",
)


@dataclass(frozen=True, slots=True)
class ResponsesPassthroughResponseSetup:
    response_id: str
    model: str
    created_at: int
    store: bool
    user_id: int | None
    api_key_id: str | None
    provider_state: ResponsesProviderState

    def storage_target(self, *, task_id: str, stream_enabled: bool) -> ResponseStorageTarget:
        return ResponseStorageTarget(
            response_id=self.response_id,
            task_id=task_id,
            user_id=self.user_id,
            api_key_id=self.api_key_id,
            model=self.model,
            created_at=self.created_at,
            is_background=False,
            stream_enabled=stream_enabled,
        )


def prepare_responses_passthrough_response_setup(
    *,
    request: Request,
    task_id: str,
    request_json: JSONDict,
) -> ResponsesPassthroughResponseSetup:
    response_id = f"resp_{task_id[-24:]}" if task_id else "resp_unknown"
    store = extract_openai_store_flag(request_json, default=True)
    api_key_id: str | None = None
    user_id: int | None = None
    if store:
        api_key_id, user_id = resolve_responses_storage_owner(request)
    request_model = request_json.get("model")
    model = request_model if isinstance(request_model, str) and request_model else "unknown"
    created_at = ms_to_seconds_floor(epoch_ms())
    return ResponsesPassthroughResponseSetup(
        response_id=response_id,
        model=model,
        created_at=created_at,
        store=store,
        user_id=user_id,
        api_key_id=api_key_id,
        provider_state=ResponsesProviderState(
            response_id=response_id,
            model=model,
            created_at=created_at,
        ),
    )
