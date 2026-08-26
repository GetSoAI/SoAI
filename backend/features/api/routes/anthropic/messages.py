"""SoAI - Anthropic-compatible Messages endpoints [backend/features/api/routes/anthropic/messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request
from starlette.responses import Response

from core.events.types_models_requests import InferenceRequestReceived
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from features.api.routes.anthropic.error_responses import project_error_response
from features.api.routes.anthropic.request_translation import (
    translate_anthropic_request,
)
from features.api.routes.anthropic.response_projection import (
    AnthropicMessageProjectionSettings,
    build_anthropic_message_from_openai_payload,
)
from features.api.routes.anthropic.stream_projection import project_anthropic_stream
from features.api.routes.openai.chat.inference_request import handle_inference_request
from features.api.routes.openai.responses.token_count_validation import (
    require_complete_responses_input_token_count,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.chat_execution.preparation import (
    prepare_openai_chat_execution,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    require_request_context_instance,
    resolve_api_context,
)
from features.api.runtime.response_body import (
    create_json_body_response,
    parse_response_body_json_dict,
)
from features.api.schemas.anthropic_messages import (
    AnthropicCountTokensRequest,
    AnthropicMessagesRequest,
)
from features.api.schemas.openai_requests import ChatCompletionRequest
from features.openai.model_aware_prompt_tokens import count_model_aware_prompt_occupancy

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict

__all__ = ("register_routes",)

_ANTHROPIC_VERSION = "2023-06-01"


def _require_anthropic_version(request: Request) -> None:
    version = (request.headers.get("anthropic-version") or "").strip()
    if version != _ANTHROPIC_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"anthropic-version must be {_ANTHROPIC_VERSION}.",
        )


async def _count_prompt_occupancy(
    request: Request,
    api_context: ApiContext,
    request_json: JSONDict,
) -> PromptOccupancy:
    dependencies = api_context.dependencies
    occupancy, _runtime_profile = await count_model_aware_prompt_occupancy(
        config=dependencies.config,
        prompt_token_counter=dependencies.prompt_token_counter,
        request_payload=request_json,
        model_resolution_service=dependencies.model_resolution_service,
        model_information_service=dependencies.model_information_service,
        model_parameter_service=dependencies.model_parameter_service,
        provider_get_external=dependencies.model_provider_coordinator.provider_get_external,
        plugin_manager=dependencies.plugin_manager,
        virtual_model_get=dependencies.model_virtual_model_service.virtual_model_get,
        state_aggregator=dependencies.state_aggregator,
        orchestrator_lifecycle=dependencies.orchestrator_lifecycle,
        request_context=require_request_context_instance(request),
    )
    require_complete_responses_input_token_count(request, occupancy)
    return occupancy


def register_routes(routers: ApiRouters) -> None:
    @routers.anthropic_public.post(
        "/messages/count_tokens",
        dependencies=[openai_api_dependency()],
    )
    async def count_tokens(
        request: Request,
        payload: AnthropicCountTokensRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        _require_anthropic_version(request)
        translation = translate_anthropic_request(payload)
        occupancy = await _count_prompt_occupancy(request, api_context, translation.request_json)
        return create_json_body_response(content={"input_tokens": occupancy.prompt_tokens})

    @routers.anthropic_public.post(
        "/messages",
        dependencies=[openai_api_dependency()],
    )
    async def messages(
        request: Request,
        payload: AnthropicMessagesRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        _require_anthropic_version(request)
        translation = translate_anthropic_request(payload)
        chat_payload = ChatCompletionRequest.model_validate(translation.request_json)
        prompt_occupancy = await _count_prompt_occupancy(
            request,
            api_context,
            translation.request_json,
        )
        prompt_tokens = prompt_occupancy.prompt_tokens

        def apply_extra_inference_parameters(
            _api_context: ApiContext,
            request_json: JSONDict,
        ) -> None:
            request_json.update(translation.extra_inference_parameters)

        prepared = await prepare_openai_chat_execution(
            request=request,
            api_context=api_context,
            request_event_class=InferenceRequestReceived,
            payload=chat_payload,
            base_capabilities=("chat_completions",),
            request_json_preprocessor=apply_extra_inference_parameters,
            prompt_count=prompt_occupancy,
        )
        if isinstance(prepared, Response):
            return project_error_response(prepared)
        projection_settings = AnthropicMessageProjectionSettings(
            model=payload.model,
            prompt_tokens=prompt_tokens,
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            structured_output_schema=translation.structured_output_schema,
            include_thinking=translation.include_thinking_in_response,
            stop_sequences=payload.stop_sequences,
        )
        if payload.stream:
            transcript = OpenAIStreamTranscript(model_hint=payload.model)

            def transform(upstream: AsyncGenerator[bytes]) -> AsyncGenerator[bytes]:
                return project_anthropic_stream(
                    upstream,
                    transcript=transcript,
                    settings=projection_settings,
                )

            response = await handle_inference_request(
                request=request,
                api_context=api_context,
                prepared_execution=prepared,
                stream_transform=transform,
            )
            if response.status_code >= 400:
                return project_error_response(response)
            return response
        response = await handle_inference_request(
            request=request,
            api_context=api_context,
            prepared_execution=prepared,
        )
        if response.status_code >= 400:
            return project_error_response(response)
        openai_payload = parse_response_body_json_dict(response, field="OpenAI completion response")
        return create_json_body_response(
            content=build_anthropic_message_from_openai_payload(
                openai_payload,
                projection_settings,
            ),
        )
