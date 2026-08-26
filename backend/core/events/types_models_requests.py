"""SoAI - Inference request received event models [backend/core/events/types_models_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.events.types_base import Event, EventDelivery, ReplyableUserCommand
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue

__all__ = (
    "AudioTranscriptionRequestReceived",
    "AudioTranslationRequestReceived",
    "EmbeddingRequestReceived",
    "ImageEditJsonRequestReceived",
    "ImageEditRequestReceived",
    "ImageGenerationRequestReceived",
    "ImageVariationRequestReceived",
    "InferenceRequestReceived",
    "TextToSpeechRequestReceived",
)


@dataclass(kw_only=True, slots=True)
class InferenceRequestReceived(Event):
    context: RequestContext
    payload: JSONDict
    reply_channel: asyncio.Queue[Event]
    task_id: str
    usage_metadata: JSONDict = field(default_factory=dict[str, JSONValue])
    delivery: EventDelivery = EventDelivery.MUST_DELIVER
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class EmbeddingRequestReceived(InferenceRequestReceived): ...


@dataclass(slots=True)
class ImageGenerationRequestReceived(InferenceRequestReceived): ...


@dataclass(slots=True)
class ImageEditJsonRequestReceived(InferenceRequestReceived): ...


@dataclass(slots=True)
class TextToSpeechRequestReceived(InferenceRequestReceived): ...


@dataclass(slots=True)
class AudioTranscriptionRequestReceived(ReplyableUserCommand):
    context: RequestContext
    temp_file_path: str
    original_filename: str
    audio_input_bytes: int | None = None
    model: str | None = None
    language: str | None = None
    prompt: str | None = None
    response_format: str | None = None
    temperature: float | None = None
    include: list[str] | None = None
    timestamp_granularities: list[str] | None = None
    stream: bool | None = None
    chunking_strategy: JSONDict | str | None = None
    known_speaker_names: list[str] | None = None
    known_speaker_references: list[str] | None = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class AudioTranslationRequestReceived(ReplyableUserCommand):
    context: RequestContext
    temp_file_path: str
    original_filename: str
    audio_input_bytes: int | None = None
    model: str | None = None
    prompt: str | None = None
    response_format: str | None = None
    temperature: float | None = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    _request_type: str = field(default="audio_translation")

    @property
    def request_type(self) -> str:
        return self._request_type


@dataclass(slots=True)
class ImageEditRequestReceived(ReplyableUserCommand):
    context: RequestContext
    image_temp_paths: tuple[str, ...]
    original_filenames: tuple[str, ...]
    prompt: str
    mask_temp_path: str | None = None
    model: str | None = None
    image_count: int | None = None
    size: str | None = None
    response_format: str | None = None
    user: str | None = None
    background: str | None = None
    output_format: str | None = None
    output_compression: int | None = None
    input_fidelity: str | None = None
    stream: bool | None = None
    partial_images: int | None = None
    quality: str | None = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    _request_type: str = field(default="image_edit")

    @property
    def request_type(self) -> str:
        return self._request_type


@dataclass(slots=True)
class ImageVariationRequestReceived(ReplyableUserCommand):
    context: RequestContext
    image_temp_path: str
    original_filename: str
    model: str | None = None
    image_count: int | None = None
    size: str | None = None
    response_format: str | None = None
    user: str | None = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    _request_type: str = field(default="image_variation")

    @property
    def request_type(self) -> str:
        return self._request_type
