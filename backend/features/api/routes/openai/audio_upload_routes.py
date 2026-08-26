"""SoAI - OpenAI audio upload endpoints [backend/features/api/routes/openai/audio_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import Response

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
)
from core.openai.audio_upload_fields import (
    OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS,
    OPENAI_AUDIO_TRANSLATION_ALLOWED_FIELDS,
)
from features.api.routes.openai.audio_upload_payloads import (
    build_openai_audio_upload_payloads,
)
from features.api.routes.openai.chat.chat_ops import (
    get_effective_routing_config,
    resolve_non_streaming_timeout,
)
from features.api.routes.openai.image_upload_quota_lifecycle import (
    make_upload_dispatch_error_handlers,
)
from features.api.routes.openai.streaming_upload_command_flow import (
    execute_openai_multipart_upload_flow,
)
from features.api.routes.openai.streaming_upload_error_handling import (
    extract_single_file,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.openai_audio_model_resolution import (
    resolve_audio_upload_model_fields,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

__all__ = ("register_routes",)


async def _handle_audio_upload_request(
    request: Request,
    *,
    api_context: ApiContext,
    event_type: type[AudioTranscriptionRequestReceived | AudioTranslationRequestReceived],
    command: str,
    operation: str,
    required_capabilities: tuple[str, ...],
    allowed_fields: frozenset[str],
) -> Response:
    max_upload_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.AUDIO,
    )
    timeout_override = resolve_non_streaming_timeout(
        get_effective_routing_config(api_context),
        None,
    )

    async def build_payload(
        _task_id: str,
        parsed: StreamingMultipartResult,
        _staged_paths: list[str],
    ) -> tuple[dict[str, JSONValue], dict[str, JSONValue]]:
        staged_part = extract_single_file(parsed.files, "file")
        fields = parsed.fields
        if event_type is AudioTranscriptionRequestReceived:
            fields = await resolve_audio_upload_model_fields(
                api_context=api_context,
                fields=parsed.fields,
                endpoint_capability="audio_transcriptions",
                unavailable_message="No transcription models available. Configure/install a plugin or provider that supports OpenAI audio transcriptions.",
            )
        payloads = build_openai_audio_upload_payloads(
            event_type=event_type,
            staged_part=staged_part,
            fields=fields,
            required_capabilities=required_capabilities,
        )
        return payloads.command_fields, payloads.quota_request_payload

    on_recoverable_dispatch_error, on_isolation_dispatch_error = (
        make_upload_dispatch_error_handlers(
            operation=operation,
            recoverable_message="Failed to dispatch OpenAI audio upload request (non-critical).",
            isolation_message="Unhandled unexpected error while dispatching OpenAI audio upload request.",
            coerce_isolation_error=True,
            details={"operation": operation},
        )
    )
    file_fields = frozenset({"file"})

    return await execute_openai_multipart_upload_flow(
        request,
        api_context=api_context,
        command_type=event_type,
        audit_action=command,
        audit_target="audio_upload",
        operation=operation,
        required_fields=frozenset(),
        allowed_fields=allowed_fields,
        required_file_fields=file_fields,
        allowed_file_fields=file_fields,
        max_file_bytes=max_upload_bytes,
        max_total_file_bytes=max_upload_bytes,
        build_payload=build_payload,
        on_recoverable_dispatch_error=on_recoverable_dispatch_error,
        on_isolation_dispatch_error=on_isolation_dispatch_error,
        response_timeout=timeout_override,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/audio/transcriptions",
        tags=["OpenAI Audio"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_audio_transcription(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await _handle_audio_upload_request(
            request,
            api_context=api_context,
            event_type=AudioTranscriptionRequestReceived,
            command="TRANSCRIBE_AUDIO",
            operation="audio.transcriptions",
            required_capabilities=("audio_transcriptions",),
            allowed_fields=OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS,
        )

    @routers.openai_public.post(
        "/audio/translations",
        tags=["OpenAI Audio"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_audio_translation(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await _handle_audio_upload_request(
            request,
            api_context=api_context,
            event_type=AudioTranslationRequestReceived,
            command="TRANSLATE_AUDIO",
            operation="audio.translations",
            required_capabilities=("audio_translations",),
            allowed_fields=OPENAI_AUDIO_TRANSLATION_ALLOWED_FIELDS,
        )
