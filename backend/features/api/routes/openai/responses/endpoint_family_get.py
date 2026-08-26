"""SoAI - OpenAI Responses endpoint get handler [backend/features/api/routes/openai/responses/endpoint_family_get.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request
from starlette.responses import Response

from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.openai.query_params import parse_openai_bool_query
from features.api.routes.openai.responses.endpoint_family_record_loading import (
    extract_stored_response_json_or_error,
    fetch_owned_response_record_for_request_or_error,
)
from features.api.routes.openai.responses.endpoint_family_response_shared import (
    create_response_not_stored_error,
    response_record_flag_enabled,
)
from features.api.routes.openai.responses.endpoint_family_streaming import (
    stream_response_events,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import apply_operation_id_header

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    router = routers.openai_public
    common_tags: list[str | Enum] = ["OpenAI Responses"]
    common_deps = [openai_api_dependency()]
    router.get(
        "/responses/{response_id}",
        tags=common_tags,
        dependencies=common_deps,
    )(get_response)


async def get_response(
    response_id: str,
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    trace_id = request.state.context.trace_id
    owned_record_or_response = await fetch_owned_response_record_for_request_or_error(
        request,
        api_context,
        response_id=response_id,
        require_stored=False,
    )
    if isinstance(owned_record_or_response, Response):
        return owned_record_or_response
    normalized_response_id, record, requesting_api_key_id, requesting_user_id = (
        owned_record_or_response
    )
    if parse_openai_bool_query(request, "stream"):
        if not response_record_flag_enabled(record, "store"):
            return create_response_not_stored_error(trace_id=trace_id)
        if not response_record_flag_enabled(record, "is_background"):
            return build_openai_error_json_response(
                status_code=400,
                message="Only background responses can be streamed by id.",
                canonical_error_type="invalid_request_error",
                param="stream",
                code=None,
                trace_id=trace_id,
                headers=None,
            )
        if not response_record_flag_enabled(record, "stream_enabled"):
            return build_openai_error_json_response(
                status_code=400,
                message="Response streaming was not enabled.",
                canonical_error_type="invalid_request_error",
                param="stream",
                code=None,
                trace_id=trace_id,
                headers=None,
            )
        return await stream_response_events(
            request=request,
            api_context=api_context,
            response_id=normalized_response_id,
            user_id=requesting_user_id,
            api_key_id=requesting_api_key_id,
        )
    response_json = extract_stored_response_json_or_error(record, trace_id=trace_id)
    if isinstance(response_json, Response):
        return response_json
    return apply_operation_id_header(
        create_json_body_response(content=response_json),
        request.state.context.trace_id,
    )
