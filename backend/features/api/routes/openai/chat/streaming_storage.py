"""SoAI - OpenAI chat streaming storage enforcement [backend/features/api/routes/openai/chat/streaming_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.protocols_database_chat_completions import (
    DatabaseOpenAIChatCompletionsProtocol,
)
from core.openai.sse_events import (
    format_openai_storage_error_chunk,
)
from core.openai.sse_frames import sse_done_chunk
from core.openai.stream_frame_processing import process_openai_stream_frame
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from features.api.routes.openai.chat.stored_payloads import (
    prepare_stored_chat_completion_payload,
)

__all__ = ("ChatCompletionStorageContext", "wrap_stream_for_chat_completion_storage")

LOGGER_NAME = "SoAI.features.api.streaming_storage"
OPERATION_FINALIZE_TRANSCRIPT = "openai.chat_completions.store.finalize_transcript"
OPERATION_PERSIST = "openai.chat_completions.store.persist"


@dataclass(frozen=True, slots=True)
class ChatCompletionStorageContext:
    database: DatabaseOpenAIChatCompletionsProtocol
    api_key_id: str | None
    task_id: str
    request_json: JSONDict


async def wrap_stream_for_chat_completion_storage(
    generator: AsyncGenerator[bytes],
    *,
    storage: ChatCompletionStorageContext,
) -> AsyncGenerator[bytes]:
    transcript = OpenAIStreamTranscript(model_hint=None, result_format="chat")
    transcript_failed = False
    stream_error_seen = False
    async for chunk in generator:
        try:
            decoded_chunk = chunk.decode("utf-8")
        except UnicodeDecodeError:
            decoded_chunk = ""
        if parse_openai_sse_error_frame(chunk) is not None:
            stream_error_seen = True
        if not transcript_failed and not stream_error_seen:
            try:
                transcript.feed(chunk)
            except RECOVERABLE_EXCEPTIONS as exception:
                transcript_failed = True
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerce_to_soai_error(
                        exception,
                        operation=OPERATION_FINALIZE_TRANSCRIPT,
                    ),
                    message="Failed to parse chat completion stream transcript.",
                    operation=OPERATION_FINALIZE_TRANSCRIPT,
                    level="warning",
                    details={"task_id": storage.task_id},
                )
        stream_frame = process_openai_stream_frame(decoded_chunk)
        if stream_frame.done_marker_observed:
            if stream_frame.filtered_text.strip():
                yield stream_frame.filtered_text.encode("utf-8")
            continue
        yield chunk
    if stream_error_seen:
        yield sse_done_chunk()
        return
    if transcript_failed:
        yield _storage_error_chunk("Stored chat completion stream could not be parsed.")
        yield sse_done_chunk()
        return
    persisted = await _persist_streamed_chat_completion(transcript, storage=storage)
    if not persisted:
        yield _storage_error_chunk("Chat completion was generated but could not be stored.")
        yield sse_done_chunk()
        return
    yield sse_done_chunk()


async def _persist_streamed_chat_completion(
    transcript: OpenAIStreamTranscript,
    *,
    storage: ChatCompletionStorageContext,
) -> bool:
    try:
        completion_json = transcript.finalize()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(exception, operation=OPERATION_FINALIZE_TRANSCRIPT),
            message="Failed to finalize chat completion stream transcript.",
            operation=OPERATION_FINALIZE_TRANSCRIPT,
            level="warning",
            details={"task_id": storage.task_id},
        )
        return False
    normalized = coerce_json_dict(completion_json) or {}
    prepared_payload = prepare_stored_chat_completion_payload(
        completion_json=normalized,
        request_json=storage.request_json,
    )
    if prepared_payload is None:
        return False
    try:
        await storage.database.upsert_chat_completion(
            completion_id=prepared_payload.completion_id,
            task_id=storage.task_id,
            api_key_id=storage.api_key_id,
            model=prepared_payload.model,
            created_at_seconds=prepared_payload.created_at_seconds,
            store=True,
            request_json=dict(storage.request_json),
            completion_json=prepared_payload.completion_json,
            metadata_json=prepared_payload.metadata_json,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(exception, operation=OPERATION_PERSIST),
            message="Failed to persist stored chat completion.",
            operation=OPERATION_PERSIST,
            level="warning",
            details={"task_id": storage.task_id, "completion_id": prepared_payload.completion_id},
        )
        return False
    return True


def _storage_error_chunk(message: str) -> bytes:
    return format_openai_storage_error_chunk(message)
