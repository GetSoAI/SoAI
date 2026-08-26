"""SoAI - OpenAI image endpoints [backend/features/api/routes/openai/images.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.events.types_models_requests import ImageGenerationRequestReceived
from features.api.routes.openai.images_request_validation import (
    preprocess_openai_image_generation_request_json,
)
from features.api.routes.openai.inference_dispatch import (
    handle_generic_inference_endpoint,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.openai_images import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/images/generations",
        tags=["OpenAI Image Generation"],
        response_model=ImageGenerationResponse,
        dependencies=[openai_api_dependency()],
    )
    async def handle_image_generation(
        request: Request,
        payload: ImageGenerationRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await handle_generic_inference_endpoint(
            request,
            api_context,
            ImageGenerationRequestReceived,
            "requests_total_image",
            payload,
            ("images",),
            request_json_preprocessor=preprocess_openai_image_generation_request_json,
        )
