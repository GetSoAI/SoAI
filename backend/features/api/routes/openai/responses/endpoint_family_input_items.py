"""SoAI - OpenAI Responses endpoint input_items handler [backend/features/api/routes/openai/responses/endpoint_family_input_items.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request
from starlette.responses import Response

from features.api.openai.query_params import parse_openai_list_query_params
from features.api.routes.openai.responses.endpoint_family_record_loading import (
    fetch_owned_response_input_items_or_error,
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
        "/responses/{response_id}/input_items",
        tags=common_tags,
        dependencies=common_deps,
    )(get_response_input_items)


async def get_response_input_items(
    response_id: str,
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    query_params = parse_openai_list_query_params(
        request,
        default_order="desc",
        default_limit=20,
        strict_order=False,
        strict_positive_limit=False,
    )
    if isinstance(query_params, Response):
        return query_params
    payload = await fetch_owned_response_input_items_or_error(
        request,
        api_context,
        response_id=response_id,
        limit=query_params.limit,
        order=query_params.order,
        after=query_params.after,
        before=query_params.before,
    )
    if isinstance(payload, Response):
        return payload
    return apply_operation_id_header(
        create_json_body_response(content=payload),
        request.state.context.trace_id,
    )
