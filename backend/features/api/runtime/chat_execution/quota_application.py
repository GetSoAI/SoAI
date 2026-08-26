"""SoAI - Chat execution quota reservation application [backend/features/api/runtime/chat_execution/quota_application.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.request_options import extract_openai_bool_flag
from core.openai.token_accounting import count_prompt_occupancy_async
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_payload_too_large
from features.api.runtime.openai_quota_reservations import reserve_token_quota_for_task
from features.api.runtime.openai_request_state import apply_openai_api_key_quota_state

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict, JSONValue

__all__ = ("apply_token_quota_reservation_to_request",)


async def apply_token_quota_reservation_to_request(
    request: Request,
    api_context: ApiContext,
    request_json: dict[str, JSONValue],
    prompt_count: PromptOccupancy | None = None,
) -> tuple[str | None, JSONDict | None, JSONResponse | None, int | None]:
    quota_payload = build_inference_request_payload(request_json)
    key_id, reservation, quota_error_response, prompt_token_count = (
        await reserve_token_quota_for_task(
            request,
            api_context,
            quota_payload,
            prompt_count=prompt_count,
        )
    )
    if prompt_token_count is None and extract_openai_bool_flag(
        request_json,
        key="stream",
        default=False,
    ):
        prompt_token_count = await count_prompt_occupancy_async(
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=quota_payload,
        )
        if prompt_token_count.capped:
            raise_payload_too_large(
                request,
                "Prompt exceeds the supported token-counting limit.",
                error_type="prompt_token_count_limit_exceeded",
            )
    prompt_tokens = prompt_token_count.prompt_tokens if prompt_token_count is not None else None
    if quota_error_response is not None:
        return (key_id, reservation, quota_error_response, prompt_tokens)
    apply_openai_api_key_quota_state(request, key_id=key_id, reservation=reservation)
    return (key_id, reservation, None, prompt_tokens)
