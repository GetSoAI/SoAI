"""SoAI - OpenAI stored chat completions endpoints [backend/features/api/routes/openai/chat/stored_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.meta.soai_v1 import SoAIV1StrictModel
from core.runtime.request_trace_id import get_request_trace_id
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.api_key_auth import require_openai_api_key_id
from features.api.openai.list_payloads import (
    build_openai_list_response,
    parse_metadata_filters,
)
from features.api.routes.openai.chat.stored_common import (
    build_chat_completion_not_found_response,
    build_invalid_after_cursor_response,
    build_stored_chat_completion_unavailable_response,
    fetch_stored_chat_completion_record_or_error,
    parse_stored_list_pagination_params,
    require_openai_api_key_and_fetch_record_or_error,
)
from features.api.routes.openai.chat.stored_payloads import (
    build_deleted_chat_completion_payload,
    build_stored_chat_completion_record_payload,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = ("register_routes",)


class ChatCompletionUpdateRequest(SoAIV1StrictModel):
    metadata: dict[str, PydanticJSONValue]


def register_routes(routers: ApiRouters) -> None:
    router = routers.openai_public
    common_deps = [openai_api_dependency()]
    common_tags: list[str | Enum] = ["Chat"]

    @router.get("/chat/completions", tags=common_tags, dependencies=common_deps)
    async def list_chat_completions(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace_id = get_request_trace_id(request)
        api_key_id_or_error = require_openai_api_key_id(request)
        if isinstance(api_key_id_or_error, JSONResponse):
            return api_key_id_or_error
        api_key_id = api_key_id_or_error
        model = coerce_optional_trimmed_str(request.query_params.get("model"))
        pagination = parse_stored_list_pagination_params(request)
        if isinstance(pagination, JSONResponse):
            return pagination
        metadata_filters = parse_metadata_filters(request)
        chat_completion_database = api_context.dependencies.database_openai_chat_completions
        if pagination.after is not None:
            cursor = await chat_completion_database.get_cursor_for_completion(
                completion_id=pagination.after,
                api_key_id=api_key_id,
            )
            if cursor is None:
                return build_invalid_after_cursor_response(
                    message="after must reference an existing stored chat completion.",
                    trace_id=trace_id,
                )
        records, has_more = await chat_completion_database.list_chat_completions(
            api_key_id=api_key_id,
            model=model,
            after=pagination.after,
            limit=pagination.limit,
            order=pagination.order,
            metadata_filters=metadata_filters,
        )
        data: list[JSONDict] = []
        for record in records:
            completion_id_value = record.get("completion_id")
            fallback_completion_id = (
                completion_id_value if isinstance(completion_id_value, str) else None
            )
            completion = build_stored_chat_completion_record_payload(
                record,
                fallback_completion_id=fallback_completion_id,
            )
            if completion is not None:
                data.append(completion)
        return build_openai_list_response(data=data, has_more=has_more)

    @router.get(
        "/chat/completions/{completion_id}",
        tags=common_tags,
        dependencies=common_deps,
    )
    async def get_chat_completion(
        completion_id: str,
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        record_or_response = await require_openai_api_key_and_fetch_record_or_error(
            request,
            api_context.dependencies.database_openai_chat_completions,
            completion_id=completion_id,
        )
        if isinstance(record_or_response, JSONResponse):
            return record_or_response
        completion = build_stored_chat_completion_record_payload(
            record_or_response,
            fallback_completion_id=completion_id,
        )
        if completion is None:
            return build_stored_chat_completion_unavailable_response(
                trace_id=get_request_trace_id(request),
            )
        return create_json_body_response(content=completion)

    @router.post(
        "/chat/completions/{completion_id}",
        tags=common_tags,
        dependencies=common_deps,
    )
    async def update_chat_completion(
        completion_id: str,
        request: Request,
        payload: ChatCompletionUpdateRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace_id = get_request_trace_id(request)
        api_key_id_or_error = require_openai_api_key_id(request)
        if isinstance(api_key_id_or_error, JSONResponse):
            return api_key_id_or_error
        api_key_id = api_key_id_or_error
        chat_completion_database = api_context.dependencies.database_openai_chat_completions
        updated = await chat_completion_database.update_chat_completion_metadata(
            completion_id=completion_id,
            api_key_id=api_key_id,
            metadata=dict(payload.metadata),
        )
        if not updated:
            return build_chat_completion_not_found_response(trace_id=trace_id)
        record_or_response = await fetch_stored_chat_completion_record_or_error(
            chat_completion_database,
            completion_id=completion_id,
            api_key_id=api_key_id,
            trace_id=trace_id,
        )
        if isinstance(record_or_response, JSONResponse):
            return record_or_response
        completion = build_stored_chat_completion_record_payload(
            record_or_response,
            fallback_completion_id=completion_id,
        )
        if completion is None:
            return build_stored_chat_completion_unavailable_response(trace_id=trace_id)
        return create_json_body_response(content=completion)

    @router.delete(
        "/chat/completions/{completion_id}",
        tags=common_tags,
        dependencies=common_deps,
    )
    async def delete_chat_completion(
        completion_id: str,
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace_id = get_request_trace_id(request)
        api_key_id_or_error = require_openai_api_key_id(request)
        if isinstance(api_key_id_or_error, JSONResponse):
            return api_key_id_or_error
        api_key_id = api_key_id_or_error
        chat_completion_database = api_context.dependencies.database_openai_chat_completions
        deleted = await chat_completion_database.mark_chat_completion_deleted(
            completion_id=completion_id,
            api_key_id=api_key_id,
        )
        if not deleted:
            return build_chat_completion_not_found_response(trace_id=trace_id)
        return create_json_body_response(
            content=build_deleted_chat_completion_payload(completion_id),
        )
