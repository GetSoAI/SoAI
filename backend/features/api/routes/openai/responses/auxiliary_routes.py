"""SoAI - OpenAI Responses input_tokens endpoint [backend/features/api/routes/openai/responses/auxiliary_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import Response

from core.openai.openai_current import RESPONSES_INPUT_TOKENS_FIELDS
from features.api.openai.request_payloads import parse_object_body_json_or_form
from features.api.routes.openai.responses.input_tokens_items import (
    build_effective_input_items_from_payload,
)
from features.api.routes.openai.responses.model_resolution import (
    resolve_responses_model_id_from_payload,
)
from features.api.routes.openai.responses.token_count_validation import (
    require_complete_responses_input_token_count,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    require_request_context_instance,
    resolve_api_context,
)
from features.api.runtime.openai_request_validation import reject_unknown_openai_fields
from features.api.runtime.response_body import create_json_body_response
from features.openai.model_aware_prompt_tokens import (
    count_model_aware_prompt_occupancy,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/responses/input_tokens",
        tags=["OpenAI Responses"],
        dependencies=[openai_api_dependency()],
    )
    async def responses_input_tokens(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        context = request.state.context
        parsed = await parse_object_body_json_or_form(request, trace_id=context.trace_id)
        if isinstance(parsed, Response):
            return parsed
        payload_json: dict[str, JSONValue] = parsed
        unknown_error = reject_unknown_openai_fields(
            payload_json,
            allowed_fields=RESPONSES_INPUT_TOKENS_FIELDS,
            trace_id=context.trace_id,
        )
        if unknown_error is not None:
            return unknown_error
        model = await resolve_responses_model_id_from_payload(
            api_context=api_context,
            trace_id=context.trace_id,
            payload_json=payload_json,
        )
        effective_items = await build_effective_input_items_from_payload(
            api_context,
            request,
            payload_json=payload_json,
        )
        if isinstance(effective_items, Response):
            return effective_items
        token_payload: dict[str, JSONValue] = {"model": model, "input": list(effective_items)}
        tools_value = payload_json.get("tools")
        if isinstance(tools_value, list):
            token_payload["tools"] = tools_value
        tool_choice_value = payload_json.get("tool_choice")
        if tool_choice_value is not None:
            token_payload["tool_choice"] = tool_choice_value
        dependencies = api_context.dependencies
        provider_coordinator = dependencies.model_provider_coordinator
        token_occupancy, _runtime_profile = await count_model_aware_prompt_occupancy(
            config=dependencies.config,
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=token_payload,
            model_resolution_service=dependencies.model_resolution_service,
            model_information_service=dependencies.model_information_service,
            model_parameter_service=dependencies.model_parameter_service,
            provider_get_external=provider_coordinator.provider_get_external,
            plugin_manager=dependencies.plugin_manager,
            virtual_model_get=dependencies.model_virtual_model_service.virtual_model_get,
            state_aggregator=dependencies.state_aggregator,
            orchestrator_lifecycle=dependencies.orchestrator_lifecycle,
            request_context=require_request_context_instance(request),
        )
        input_tokens_value = require_complete_responses_input_token_count(
            request,
            token_occupancy,
        )
        return create_json_body_response(
            content={
                "object": "response.input_tokens",
                "input_tokens": input_tokens_value,
            },
        )
