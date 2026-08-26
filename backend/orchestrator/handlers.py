"""SoAI - Orchestrator request handlers [backend/orchestrator/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
    ImageEditRequestReceived,
    ImageVariationRequestReceived,
    InferenceRequestReceived,
)
from core.metrics.usage import USAGE_METADATA_AUDIO_INPUT_BYTES
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.runtime.shutdown_errors import SERVER_SHUTTING_DOWN_MESSAGE
from core.tasks.failure_events import send_error_event
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task_cancellation import cancel
from orchestrator.internal_protocols import EventWithContextAndReplyProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "OrchestratorHandlers",
    "OrchestratorHandlersDependencies",
)


@dataclass(frozen=True, slots=True)
class OrchestratorHandlersDependencies:
    queue: OrchestratorQueueProtocol
    is_quiescent: asyncio.Event
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorHandlersDependencies",
            is_quiescent=self.is_quiescent,
            queue=self.queue,
            task_registry=self.task_registry,
        )


class OrchestratorHandlers:
    def __init__(self, deps: OrchestratorHandlersDependencies) -> None:
        self._deps = deps

    def _build_inference_request(
        self,
        *,
        event: EventWithContextAndReplyProtocol,
        task_id: str,
        payload: Mapping[str, JSONValue],
        usage_metadata: Mapping[str, JSONValue] | None = None,
    ) -> InferenceRequestReceived:
        return InferenceRequestReceived(
            context=event.context,
            payload=dict(payload),
            reply_channel=event.reply_channel,
            task_id=task_id,
            usage_metadata=dict(usage_metadata or {}),
            required_capabilities=event.required_capabilities,
            required_modalities=event.required_modalities,
        )

    async def _require_task_id(
        self,
        event: EventWithContextAndReplyProtocol,
        missing_message: str,
    ) -> str | None:
        if self._deps.is_quiescent.is_set():
            await send_error_event(
                event.reply_channel,
                SERVER_SHUTTING_DOWN_MESSAGE,
                ErrorType.SERVICE_UNAVAILABLE,
                context=event.context,
            )
            task_id = event.context.task_id
            if isinstance(task_id, str) and task_id.strip():
                await cancel(
                    self._deps.task_registry,
                    task_id,
                    reason=SERVER_SHUTTING_DOWN_MESSAGE,
                    context=event.context,
                )
            return None
        task_id = event.context.task_id
        if not isinstance(task_id, str) or not task_id.strip():
            await send_error_event(
                event.reply_channel,
                missing_message,
                ErrorType.INVALID_REQUEST,
                context=event.context,
            )
            return None
        return task_id

    async def handle_audio_transcription_request(
        self,
        event: AudioTranscriptionRequestReceived,
    ) -> InferenceRequestReceived | None:
        task_id = await self._require_task_id(
            event,
            "Missing task_id for audio transcription request.",
        )
        if not task_id:
            return None
        payload: dict[str, JSONValue] = {
            "_request_type": "audio_transcription",
            "model": event.model,
            "temp_file_path": event.temp_file_path,
            "original_filename": event.original_filename,
        }
        if event.language is not None:
            payload["language"] = event.language
        if event.prompt is not None:
            payload["prompt"] = event.prompt
        if event.response_format is not None:
            payload["response_format"] = event.response_format
        if event.temperature is not None:
            payload["temperature"] = event.temperature
        if event.include:
            payload["include"] = event.include
        if event.timestamp_granularities:
            payload["timestamp_granularities"] = event.timestamp_granularities
        if event.stream is not None:
            payload["stream"] = event.stream
        if event.chunking_strategy is not None:
            payload["chunking_strategy"] = event.chunking_strategy
        if event.known_speaker_names:
            payload["known_speaker_names"] = event.known_speaker_names
        if event.known_speaker_references:
            payload["known_speaker_references"] = event.known_speaker_references
        return self._build_inference_request(
            event=event,
            task_id=task_id,
            payload=payload,
            usage_metadata=_build_audio_usage_metadata(event.audio_input_bytes),
        )

    async def handle_audio_translation_request(
        self,
        event: AudioTranslationRequestReceived,
    ) -> InferenceRequestReceived | None:
        task_id = await self._require_task_id(
            event,
            "Missing task_id for audio translation request.",
        )
        if not task_id:
            return None
        payload: dict[str, JSONValue] = {
            "_request_type": event.request_type,
            "model": event.model,
            "temp_file_path": event.temp_file_path,
            "original_filename": event.original_filename,
        }
        if event.prompt is not None:
            payload["prompt"] = event.prompt
        if event.response_format is not None:
            payload["response_format"] = event.response_format
        if event.temperature is not None:
            payload["temperature"] = event.temperature
        return self._build_inference_request(
            event=event,
            task_id=task_id,
            payload=payload,
            usage_metadata=_build_audio_usage_metadata(event.audio_input_bytes),
        )

    async def handle_image_edit_request(
        self,
        event: ImageEditRequestReceived,
    ) -> InferenceRequestReceived | None:
        task_id = await self._require_task_id(event, "Missing task_id for image edit request.")
        if not task_id:
            return None
        payload: dict[str, JSONValue] = {
            "_request_type": event.request_type,
            "model": event.model,
            "image_temp_paths": list(event.image_temp_paths),
            "original_filenames": list(event.original_filenames),
            "prompt": event.prompt,
        }
        if event.mask_temp_path is not None:
            payload["mask_temp_path"] = event.mask_temp_path
        if event.image_count is not None:
            payload["n"] = event.image_count
        if event.size is not None:
            payload["size"] = event.size
        if event.response_format is not None:
            payload["response_format"] = event.response_format
        if event.user is not None:
            payload["user"] = event.user
        if event.background is not None:
            payload["background"] = event.background
        if event.output_format is not None:
            payload["output_format"] = event.output_format
        if event.output_compression is not None:
            payload["output_compression"] = event.output_compression
        if event.input_fidelity is not None:
            payload["input_fidelity"] = event.input_fidelity
        if event.stream is not None:
            payload["stream"] = event.stream
        if event.partial_images is not None:
            payload["partial_images"] = event.partial_images
        if event.quality is not None:
            payload["quality"] = event.quality
        return self._build_inference_request(
            event=event,
            task_id=task_id,
            payload=payload,
        )

    async def handle_image_variation_request(
        self,
        event: ImageVariationRequestReceived,
    ) -> InferenceRequestReceived | None:
        task_id = await self._require_task_id(event, "Missing task_id for image variation request.")
        if not task_id:
            return None
        payload: dict[str, JSONValue] = {
            "_request_type": event.request_type,
            "model": event.model,
            "image_temp_path": event.image_temp_path,
            "original_filename": event.original_filename,
        }
        if event.image_count is not None:
            payload["n"] = event.image_count
        if event.size is not None:
            payload["size"] = event.size
        if event.response_format is not None:
            payload["response_format"] = event.response_format
        if event.user is not None:
            payload["user"] = event.user
        return self._build_inference_request(
            event=event,
            task_id=task_id,
            payload=payload,
        )


def _build_audio_usage_metadata(audio_input_bytes: int | None) -> dict[str, JSONValue]:
    if audio_input_bytes is None:
        return {}
    return {USAGE_METADATA_AUDIO_INPUT_BYTES: audio_input_bytes}
