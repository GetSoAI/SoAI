"""SoAI - OpenAI chat completions endpoint [backend/features/api/routes/openai/chat/endpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.events.types_models_requests import InferenceRequestReceived
from features.api.routes.openai.inference_dispatch import (
    handle_generic_inference_endpoint,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.openai_requests import ChatCompletionRequest

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/chat/completions",
        tags=["OpenAI Completions"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_chat_completions(
        request: Request,
        payload: ChatCompletionRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await handle_generic_inference_endpoint(
            request,
            api_context,
            InferenceRequestReceived,
            "requests_total_chat_completions",
            payload,
            ("chat_completions",),
        )
