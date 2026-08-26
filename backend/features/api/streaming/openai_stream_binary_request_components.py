"""SoAI - OpenAI binary streaming request orchestration components [backend/features/api/streaming/openai_stream_binary_request_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from fastapi import Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_files import FileContentQuery
from core.events.types_models_requests import TextToSpeechRequestReceived
from core.runtime.request_context import RequestContext
from core.serialization.json import normalize_for_json
from core.tasks.type_catalog import (
    TaskTypeId,
    is_orchestrated_inference_task_type,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.openai_quota_reservations import (
    release_token_quota_reservation_if_present,
    reserve_token_quota_for_task,
)
from features.api.runtime.task_metadata import build_inference_task_metadata

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_streaming_request_event",
    "build_streaming_task_metadata",
    "coerce_streaming_queue_maxsize",
    "normalize_streaming_request_payload",
    "release_streaming_quota_reservation",
    "resolve_streaming_quota",
)


def normalize_streaming_request_payload(payload: BaseModel | Mapping[str, JSONValue]) -> JSONDict:
    if isinstance(payload, BaseModel):
        raw_payload = payload.model_dump(exclude_none=True)
    elif isinstance(payload, Mapping):
        raw_payload = {str(key): value for key, value in payload.items()}
    else:
        raise ValidationError("Streaming payload must be a Pydantic model or mapping.")
    return {str(key): normalize_for_json(value) for key, value in raw_payload.items()}


async def resolve_streaming_quota(
    request: Request,
    api_context: ApiContext,
    *,
    task_type: TaskTypeId,
    payload_dict: JSONDict,
) -> tuple[str | None, JSONDict | None, JSONResponse | None, PromptOccupancy | None]:
    if not is_orchestrated_inference_task_type(task_type):
        return (None, None, None, None)
    key_id, reservation, quota_error_response, prompt_count = await reserve_token_quota_for_task(
        request,
        api_context,
        payload_dict,
    )
    return (
        key_id,
        reservation,
        quota_error_response,
        prompt_count,
    )


def build_streaming_task_metadata(
    context: RequestContext,
    request: Request,
    model_name: str | None,
    request_event_class: type[TextToSpeechRequestReceived | FileContentQuery],
    *,
    prompt_count: PromptOccupancy | None = None,
) -> JSONDict:
    metadata: JSONDict = build_inference_task_metadata(
        context,
        request,
        model_name,
        request_event_class.__name__,
    )
    if prompt_count is None:
        return metadata
    metadata["prompt_tokens"] = prompt_count.prompt_tokens
    metadata["prompt_tokens_precision"] = prompt_count.precision
    if prompt_count.capped:
        metadata["prompt_tokens_capped"] = True
    if prompt_count.capped_reason:
        metadata["prompt_tokens_capped_reason"] = prompt_count.capped_reason
    return metadata


def build_streaming_request_event(
    request_event_class: type[TextToSpeechRequestReceived | FileContentQuery],
    *,
    context: RequestContext,
    payload_dict: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    base_capabilities: Iterable[str] | None = None,
    base_modalities: Iterable[str] | None = None,
    request_user_id: int | None = None,
    request_api_key_id: str | None = None,
) -> Event:
    if request_event_class is TextToSpeechRequestReceived:
        return TextToSpeechRequestReceived(
            context=context,
            payload=payload_dict,
            reply_channel=reply_queue,
            task_id=task_id,
            required_capabilities=tuple(base_capabilities or ()),
            required_modalities=tuple(base_modalities or ()),
        )
    if request_event_class is FileContentQuery:
        return FileContentQuery(
            context=context,
            payload=payload_dict,
            reply_channel=reply_queue,
            user_id=request_user_id,
            api_key_id=request_api_key_id,
        )
    raise ValidationError("Unsupported request_event_class for binary streaming request.")


def coerce_streaming_queue_maxsize(queue_maxsize: int) -> int:
    if isinstance(queue_maxsize, bool):
        return 1000
    try:
        normalized = int(queue_maxsize)
    except (TypeError, ValueError):
        return 1000
    if normalized < 1:
        return 1
    if normalized > 10000:
        return 10000
    return normalized


async def release_streaming_quota_reservation(
    api_context: ApiContext,
    key_id: str | None,
    reservation: JSONDict | None,
    *,
    trace_id: str | None,
    operation: str,
) -> None:
    await release_token_quota_reservation_if_present(
        api_context,
        key_id,
        reservation,
        trace_id=trace_id,
        operation=operation,
    )
