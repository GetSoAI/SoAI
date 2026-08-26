"""SoAI - OpenAI audio speech endpoint [backend/features/api/routes/openai/audio_speech_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.events.types_models_requests import TextToSpeechRequestReceived
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.openai_tts_request_preparation import (
    prepare_text_to_speech_request,
)
from features.api.schemas.openai_audio import TextToSpeechRequest
from features.api.streaming.openai_stream_binary_request_handler import (
    handle_streaming_binary_request,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/audio/speech",
        tags=["OpenAI Audio"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_text_to_speech(
        request: Request,
        payload: TextToSpeechRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        metrics_manager = api_context.dependencies.metrics_manager
        metrics_manager.increment_counter("api", "openai", "requests_total_tts")
        prepared = await prepare_text_to_speech_request(
            api_context=api_context,
            request=payload,
            include_input=True,
        )
        return await handle_streaming_binary_request(
            request,
            prepared.payload,
            TextToSpeechRequestReceived,
            prepared.media_type,
            api_context=api_context,
            base_capabilities=("audio_speech",),
            stream_format=prepared.request.stream_format,
            resolved_model_id=prepared.resolved_model_id,
        )
