"""SoAI - OpenAI embeddings endpoint [backend/features/api/routes/openai/embeddings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.events.types_models_requests import EmbeddingRequestReceived
from features.api.routes.openai.inference_dispatch import (
    handle_generic_inference_endpoint,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.openai_requests import EmbeddingRequest

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/embeddings",
        tags=["OpenAI Embeddings"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_embeddings(
        request: Request,
        payload: EmbeddingRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await handle_generic_inference_endpoint(
            request,
            api_context,
            EmbeddingRequestReceived,
            "requests_total_embedding",
            payload,
            ("embeddings",),
        )
