"""SoAI - OpenAI Responses streaming helpers [backend/features/api/routes/openai/responses/endpoint_family_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.response_terminal_policy import is_terminal_response_payload
from core.openai.responses_events import coerce_response_created_at
from core.openai.sse_events import format_openai_sse_data
from core.openai.sse_frames import sse_done_chunk
from core.timing.epoch import epoch_seconds
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.query_params import parse_openai_int_query
from features.api.routes.openai.responses.streaming_generator.persistence import (
    build_failed_event_done_chunks,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import build_task_operation_headers
from features.api.streaming.sse_responses import create_sse_response

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

__all__ = (
    "create_response_events_stream",
    "stream_response_events",
)

LOGGER_NAME = "SoAI.features.api.endpoint_family_streaming"
OPERATION = "openai.responses.stream_events"


def create_response_events_stream(
    *,
    request: Request,
    api_context: ApiContext,
    response_id: str,
    starting_after: int,
    limit: int,
    user_id: int | None,
    api_key_id: str | None,
    additional_headers: dict[str, str] | None,
) -> Response:
    poll_interval_seconds = 0.1

    async def generator() -> AsyncGenerator[str | bytes]:
        cursor = int(starting_after)
        trace_id: str | None = None
        request_context = None
        try:
            request_context = request.state.context
        except AttributeError:
            request_context = None
        if request_context is not None:
            try:
                trace_id = coerce_optional_trimmed_str(request_context.trace_id)
            except AttributeError:
                trace_id = None
        resolved_model = "unknown"
        resolved_created_at: int | None = None
        try:
            record = await api_context.dependencies.database_openai_responses.get_response_record(
                response_id=response_id,
                user_id=user_id,
                api_key_id=api_key_id,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to load response record for synthetic SSE events (non-critical).",
                trace_id=trace_id,
                operation=OPERATION,
                details={"response_id": response_id},
                level="debug",
            )
            record = None
        if isinstance(record, dict):
            response_json_value = record.get("response_json")
            response_json = coerce_json_dict(response_json_value)
            if response_json is not None:
                model_value = response_json.get("model")
                normalized_model = (
                    model_value.strip()
                    if isinstance(model_value, str) and model_value.strip()
                    else None
                )
                if normalized_model is not None:
                    resolved_model = normalized_model
                created_at_value = response_json.get("created_at")
                resolved_created_at = coerce_response_created_at(
                    created_at_value,
                    default=resolved_created_at or 0,
                )
                if resolved_created_at <= 0:
                    resolved_created_at = None
            if resolved_model == "unknown":
                model_value = record.get("model")
                normalized_model = (
                    model_value.strip()
                    if isinstance(model_value, str) and model_value.strip()
                    else None
                )
                if normalized_model is not None:
                    resolved_model = normalized_model
            if resolved_created_at is None:
                created_at_ms_value = record.get("created_at_ms")
                if isinstance(created_at_ms_value, int) and created_at_ms_value > 0:
                    resolved_created_at = int(created_at_ms_value // 1000)
        if resolved_created_at is None:
            resolved_created_at = int(epoch_seconds())
        try:
            while True:
                if await request.is_disconnected():
                    yield sse_done_chunk()
                    return
                if api_context.dependencies.shutdown_event.is_set():
                    failed_chunk, done_chunk = build_failed_event_done_chunks(
                        response_id=response_id,
                        message="SoAI API Server is shutting down.",
                        code="server_error",
                        model=resolved_model,
                        created_at=resolved_created_at,
                    )
                    yield failed_chunk
                    yield done_chunk
                    return
                events, _has_more = (
                    await api_context.dependencies.database_openai_responses.list_events_after(
                        response_id=response_id,
                        starting_after=cursor,
                        limit=limit,
                        user_id=user_id,
                        api_key_id=api_key_id,
                    )
                )
                for event in events:
                    sequence_value = event.get("sequence_number")
                    if isinstance(sequence_value, int):
                        cursor = max(cursor, int(sequence_value))
                    else:
                        cursor += 1
                    yield format_openai_sse_data(event)
                    if is_terminal_response_payload(event):
                        yield sse_done_chunk()
                        return
                await asyncio.sleep(poll_interval_seconds)
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Failed to load response events.",
                trace_id=trace_id,
                operation=OPERATION,
                details={
                    "response_id": response_id,
                    "starting_after": starting_after,
                    "limit": limit,
                },
            )
            failed_chunk, done_chunk = build_failed_event_done_chunks(
                response_id=response_id,
                message="Failed to load response events.",
                code="server_error",
                model=resolved_model,
                created_at=resolved_created_at,
            )
            yield failed_chunk
            yield done_chunk
            return

    context = request.state.context
    headers = build_task_operation_headers(task_id=None, operation_id=context.trace_id)
    if additional_headers:
        headers.update(additional_headers)
    return create_sse_response(
        generator(),
        additional_headers=dict(headers),
    )


async def stream_response_events(
    *,
    request: Request,
    api_context: ApiContext,
    response_id: str,
    user_id: int | None,
    api_key_id: str | None,
) -> Response:
    starting_after = parse_openai_int_query(request, "starting_after", -1)
    limit = parse_openai_int_query(request, "limit", 1000)
    return create_response_events_stream(
        request=request,
        api_context=api_context,
        response_id=response_id,
        starting_after=starting_after,
        limit=limit,
        user_id=user_id,
        api_key_id=api_key_id,
        additional_headers=None,
    )
