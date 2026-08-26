"""SoAI - Stored chat completion persistence helpers [backend/features/api/routes/openai/chat/chat_completion_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_trace_id import get_request_trace_id
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.routes.openai.chat.stored_payloads import (
    prepare_stored_chat_completion_payload,
)
from features.api.routes.openai.chat.streaming_storage import (
    ChatCompletionStorageContext,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.response_body import parse_response_body_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_storage_context_for_stream",
    "store_non_streaming_chat_completion",
)

LOGGER_NAME = "SoAI.features.api.chat_completion_storage"
OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PERSIST_NON_STREAM = (
    "openai.chat_completions.store.persist_non_stream"
)
OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PARSE_NON_STREAM = (
    "openai.chat_completions.store.parse_non_stream"
)


def build_storage_context_for_stream(
    *,
    api_context: ApiContext,
    api_key_id: str | None,
    task_id: str,
    request_json: JSONDict,
    enabled: bool,
) -> ChatCompletionStorageContext | None:
    if not enabled:
        return None
    return ChatCompletionStorageContext(
        database=api_context.dependencies.database_openai_chat_completions,
        api_key_id=api_key_id,
        task_id=task_id,
        request_json=request_json,
    )


async def store_non_streaming_chat_completion(
    *,
    api_context: ApiContext,
    api_key_id: str | None,
    task_id: str,
    request_json: JSONDict,
    response: Response,
) -> JSONResponse | None:
    logger = get_logger(LOGGER_NAME)
    if response.status_code != 200:
        return None
    try:
        decoded = parse_response_body_json_value(
            response,
            field="stored chat completion response",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        trace_id = get_request_trace_id(api_context.request)
        log_exception(
            logger,
            coerce_to_soai_error(
                exception,
                operation=OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PARSE_NON_STREAM,
                trace_id=trace_id,
            ),
            operation=OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PARSE_NON_STREAM,
            message="Failed to parse stored chat completion response.",
            trace_id=trace_id,
            level="warning",
            details={"task_id": task_id},
        )
        return _build_storage_failure_response(api_context)
    if not isinstance(decoded, dict):
        return _build_storage_failure_response(api_context)
    prepared_payload = prepare_stored_chat_completion_payload(
        completion_json=dict(decoded),
        request_json=request_json,
    )
    if prepared_payload is None:
        completion_id_value = decoded.get("id")
        requested_model = request_json.get("model")
        if (
            isinstance(completion_id_value, str)
            and completion_id_value.strip()
            and (not isinstance(requested_model, str) or not requested_model.strip())
        ):
            logger.warning(
                "Stored chat completion missing model; failing store=true request (completion_id=%s task_id=%s).",
                completion_id_value,
                task_id,
            )
        return _build_storage_failure_response(api_context)
    try:
        await api_context.dependencies.database_openai_chat_completions.upsert_chat_completion(
            completion_id=prepared_payload.completion_id,
            task_id=task_id,
            api_key_id=api_key_id,
            model=prepared_payload.model,
            created_at_seconds=prepared_payload.created_at_seconds,
            store=True,
            request_json=dict(request_json),
            completion_json=prepared_payload.completion_json,
            metadata_json=prepared_payload.metadata_json,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        trace_id = get_request_trace_id(api_context.request)
        log_exception(
            logger,
            coerce_to_soai_error(
                exception,
                operation=OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PERSIST_NON_STREAM,
                trace_id=trace_id,
            ),
            operation=OPERATION_OPENAI_CHAT_COMPLETIONS_STORE_PERSIST_NON_STREAM,
            message="Failed to persist stored chat completion.",
            trace_id=trace_id,
            level="warning",
            details={"completion_id": prepared_payload.completion_id, "task_id": task_id},
        )
        return _build_storage_failure_response(api_context)
    return None


def _build_storage_failure_response(api_context: ApiContext) -> JSONResponse:
    return build_openai_error_json_response_for_status(
        status_code=500,
        message="Chat completion was generated but could not be stored.",
        soai_code="storage_failed",
        param=None,
        trace_id=get_request_trace_id(api_context.request),
    )
