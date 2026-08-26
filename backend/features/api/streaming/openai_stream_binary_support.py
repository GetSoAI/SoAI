"""SoAI - OpenAI streaming binary chunk normalization helpers [backend/features/api/streaming/openai_stream_binary_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_files import FileContentQuery
from core.events.types_models_requests import TextToSpeechRequestReceived
from core.openai.stream_chunk_bytes import coerce_stream_chunk_to_bytes
from core.tasks.type_catalog import (
    TASK_TYPE_BACKGROUND_JOB,
    TASK_TYPE_TEXT_TO_SPEECH,
    TaskTypeId,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "normalize_binary_chunk",
    "resolve_binary_task_type",
)


def normalize_binary_chunk(chunk: StreamChunk) -> bytes | None:
    try:
        return coerce_stream_chunk_to_bytes(chunk)
    except ValidationError:
        return None


def resolve_binary_task_type(
    request_event_class: type[TextToSpeechRequestReceived | FileContentQuery],
) -> TaskTypeId:
    if request_event_class is TextToSpeechRequestReceived:
        return TASK_TYPE_TEXT_TO_SPEECH
    if request_event_class is FileContentQuery:
        return TASK_TYPE_BACKGROUND_JOB
    raise ValidationError(
        f"Unsupported streaming request event type: {request_event_class.__name__}",
    )
