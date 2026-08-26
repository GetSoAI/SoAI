"""SoAI - WebSocket chat task metadata shaping [backend/features/api/runtime/chat_execution/task_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import (
    PromptOccupancy,
    build_prompt_occupancy_metadata,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "build_ws_chat_stream_task_metadata",
    "build_ws_chat_stream_task_metadata_from_prompt_occupancy",
)


def build_ws_chat_stream_task_metadata(
    *,
    runtime: AssistantTimelineRuntime,
    internal_status_preview: bool = False,
) -> JSONDict:
    task_metadata = _build_ws_chat_stream_base_task_metadata(runtime)
    if internal_status_preview:
        task_metadata["internal_status_preview"] = True
        return task_metadata
    prompt_occupancy = _resolve_runtime_prompt_occupancy(runtime)
    if prompt_occupancy is not None:
        task_metadata.update(build_prompt_occupancy_metadata(prompt_occupancy))
    return task_metadata


def build_ws_chat_stream_task_metadata_from_prompt_occupancy(
    *,
    runtime: AssistantTimelineRuntime,
    prompt_occupancy: PromptOccupancy,
) -> JSONDict:
    task_metadata = _build_ws_chat_stream_base_task_metadata(runtime)
    task_metadata.update(build_prompt_occupancy_metadata(prompt_occupancy))
    return task_metadata


def _build_ws_chat_stream_base_task_metadata(
    runtime: AssistantTimelineRuntime,
) -> JSONDict:
    task_metadata: JSONDict = {
        "webui": True,
        "conv_id": runtime.conv_id,
        "request_id": runtime.request_id,
    }
    if runtime.quota_key_id is not None:
        task_metadata["api_key_id"] = runtime.quota_key_id
    if runtime.quota_token_reservation is not None:
        task_metadata["quota"] = runtime.quota_token_reservation
    return task_metadata


def _resolve_runtime_prompt_occupancy(
    runtime: AssistantTimelineRuntime,
) -> PromptOccupancy | None:
    if runtime.quota_prompt_tokens is not None and (
        isinstance(runtime.quota_prompt_tokens, bool)
        or not isinstance(runtime.quota_prompt_tokens, int)
        or runtime.quota_prompt_tokens < 0
    ):
        raise ValidationError("Runtime quota prompt tokens must be a non-negative integer.")
    if (
        isinstance(runtime.usage_preview_prompt_tokens, bool)
        or not isinstance(runtime.usage_preview_prompt_tokens, int)
        or runtime.usage_preview_prompt_tokens < 0
    ):
        raise ValidationError("Runtime usage preview prompt tokens must be a non-negative integer.")
    if runtime.quota_prompt_tokens is not None:
        prompt_tokens = int(runtime.quota_prompt_tokens)
    elif runtime.usage_preview_prompt_tokens > 0:
        prompt_tokens = int(runtime.usage_preview_prompt_tokens)
    else:
        return None
    capped_reason_value = runtime.usage_preview_prompt_tokens_capped_reason
    return PromptOccupancy(
        prompt_tokens=prompt_tokens,
        capped=runtime.usage_preview_prompt_tokens_capped,
        capped_reason=(
            capped_reason_value.strip()
            if isinstance(capped_reason_value, str) and capped_reason_value.strip()
            else None
        ),
        precision=runtime.usage_preview_prompt_precision,
    )
