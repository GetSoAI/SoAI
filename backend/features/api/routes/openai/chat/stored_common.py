"""SoAI - Shared helpers for stored chat completion endpoints [backend/features/api/routes/openai/chat/stored_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.runtime.request_trace_id import get_request_trace_id
from core.types.json import JSONDict
from features.api.openai.api_key_auth import require_openai_api_key_id
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.openai.query_params import (
    OpenAIListQueryParams,
    parse_openai_list_query_params,
)

if TYPE_CHECKING:
    from core.openai.protocols_database_chat_completions import (
        DatabaseOpenAIChatCompletionsProtocol,
    )

__all__ = (
    "build_chat_completion_not_found_response",
    "build_invalid_after_cursor_response",
    "build_stored_chat_completion_unavailable_response",
    "fetch_stored_chat_completion_record_or_error",
    "parse_stored_list_pagination_params",
    "require_openai_api_key_and_fetch_record_or_error",
)


def build_chat_completion_not_found_response(*, trace_id: str | None) -> JSONResponse:
    return build_openai_error_json_response(
        status_code=404,
        message="Chat completion not found.",
        canonical_error_type="invalid_request_error",
        param="completion_id",
        code=None,
        trace_id=trace_id,
        headers=None,
    )


def build_stored_chat_completion_unavailable_response(*, trace_id: str | None) -> JSONResponse:
    return build_openai_error_json_response(
        status_code=502,
        message="Stored chat completion is unavailable.",
        canonical_error_type="server_error",
        param=None,
        code=None,
        trace_id=trace_id,
        headers=None,
    )


def build_invalid_after_cursor_response(
    *,
    message: str,
    trace_id: str | None,
) -> JSONResponse:
    return build_openai_error_json_response(
        status_code=400,
        message=message,
        canonical_error_type="invalid_request_error",
        param="after",
        code=None,
        trace_id=trace_id,
        headers=None,
    )


async def fetch_stored_chat_completion_record_or_error(
    database: DatabaseOpenAIChatCompletionsProtocol,
    *,
    completion_id: str,
    api_key_id: str,
    trace_id: str | None,
) -> JSONDict | JSONResponse:
    record = await database.get_chat_completion_record(
        completion_id=completion_id,
        api_key_id=api_key_id,
    )
    if record is None:
        return build_chat_completion_not_found_response(trace_id=trace_id)
    return record


async def require_openai_api_key_and_fetch_record_or_error(
    request: Request,
    database: DatabaseOpenAIChatCompletionsProtocol,
    *,
    completion_id: str,
) -> JSONDict | JSONResponse:
    api_key_id_or_error = require_openai_api_key_id(request)
    if isinstance(api_key_id_or_error, JSONResponse):
        return api_key_id_or_error
    return await fetch_stored_chat_completion_record_or_error(
        database,
        completion_id=completion_id,
        api_key_id=api_key_id_or_error,
        trace_id=get_request_trace_id(request),
    )


def parse_stored_list_pagination_params(
    request: Request,
) -> OpenAIListQueryParams | JSONResponse:
    return parse_openai_list_query_params(
        request,
        default_order="asc",
        default_limit=20,
        strict_order=True,
        strict_positive_limit=True,
    )
