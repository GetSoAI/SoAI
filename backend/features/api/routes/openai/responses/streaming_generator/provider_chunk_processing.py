"""SoAI - OpenAI Responses provider chunk processing [backend/features/api/routes/openai/responses/streaming_generator/provider_chunk_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.openai.response_terminal_policy import is_terminal_response_payload
from core.openai.responses_provider_events import (
    ResponsesProviderStreamError,
    decode_responses_provider_frame,
)
from core.types.json_value import coerce_json_dict
from features.api.routes.openai.responses.streaming_generator.terminal_events import (
    emit_failure_done,
)

if TYPE_CHECKING:
    from core.openai.responses_provider_state import (
        ResponsesProviderState,
    )
    from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
    from core.types.json import JSONDict
    from features.api.routes.openai.responses.streaming_generator.passthrough_persistence import (
        ResponsesPassthroughPersistence,
    )

__all__ = (
    "ProviderChunkProcessingResult",
    "collect_provider_chunk_response_events",
    "finalize_provider_sse_stream",
)


@dataclass(frozen=True, slots=True)
class ProviderChunkProcessingResult:
    emitted_chunks: tuple[bytes, ...]
    terminal: bool
    observed_provider_payload: bool


async def _collect_failure_chunks(
    *,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
    message: str,
) -> tuple[bytes, ...]:
    chunks: list[bytes] = []
    async for chunk in emit_failure_done(
        persistence=persistence,
        done_chunk=done_chunk,
        code="server_error",
        message=message,
    ):
        chunks.append(chunk)
    return tuple(chunks)


async def _build_failure_result(
    *,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
    message: str,
) -> ProviderChunkProcessingResult:
    return ProviderChunkProcessingResult(
        emitted_chunks=await _collect_failure_chunks(
            persistence=persistence,
            done_chunk=done_chunk,
            message=message,
        ),
        terminal=True,
        observed_provider_payload=False,
    )


async def finalize_provider_sse_stream(
    *,
    accumulator: OpenAISSEFrameAccumulator,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
) -> tuple[bytes, ...]:
    try:
        accumulator.finalize()
    except ModelOutputContractError:
        return await _collect_failure_chunks(
            persistence=persistence,
            done_chunk=done_chunk,
            message="Provider ended with an incomplete Responses SSE frame.",
        )
    return ()


async def collect_provider_chunk_response_events(
    *,
    chunk: bytes,
    accumulator: OpenAISSEFrameAccumulator,
    provider_state: ResponsesProviderState,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
) -> ProviderChunkProcessingResult:
    emitted_chunks: list[bytes] = []
    observed_provider_payload = False
    try:
        frames = accumulator.feed(chunk)
    except ModelOutputContractError:
        return await _build_failure_result(
            persistence=persistence,
            done_chunk=done_chunk,
            message="Provider returned an invalid Responses SSE byte stream.",
        )
    decoded_payloads: list[JSONDict] = []
    terminal_observed = False
    done_observed = False
    for frame in frames:
        try:
            decoded_frame = decode_responses_provider_frame(frame)
        except ResponsesProviderStreamError:
            return await _build_failure_result(
                persistence=persistence,
                done_chunk=done_chunk,
                message="Provider returned a malformed Responses SSE frame.",
            )
        for payload in decoded_frame.payloads:
            if terminal_observed or done_observed:
                return await _build_failure_result(
                    persistence=persistence,
                    done_chunk=done_chunk,
                    message="Provider emitted a Responses payload after its terminal event.",
                )
            if (
                is_terminal_response_payload(payload)
                and coerce_json_dict(payload.get("response")) is None
            ):
                return await _build_failure_result(
                    persistence=persistence,
                    done_chunk=done_chunk,
                    message="Provider returned a malformed terminal Responses event.",
                )
            decoded_payloads.append(dict(payload))
            if is_terminal_response_payload(payload):
                terminal_observed = True
        if decoded_frame.done_observed:
            if not terminal_observed:
                return await _build_failure_result(
                    persistence=persistence,
                    done_chunk=done_chunk,
                    message="Provider ended the Responses stream without a terminal response event.",
                )
            done_observed = True
    if terminal_observed and accumulator.pending_byte_count() > 0:
        return await _build_failure_result(
            persistence=persistence,
            done_chunk=done_chunk,
            message="Provider emitted bytes after its terminal Responses event.",
        )
    for payload in decoded_payloads:
        normalized_payload = provider_state.normalize_event_indexes(dict(payload))
        provider_state.observe(normalized_payload)
        observed_provider_payload = True
        event_bytes, terminal = persistence.emit_response_event(payload=normalized_payload)
        await persistence.flush_if_needed(force=bool(terminal))
        emitted_chunks.append(event_bytes)
        if terminal:
            emitted_chunks.append(done_chunk)
            return ProviderChunkProcessingResult(
                emitted_chunks=tuple(emitted_chunks),
                terminal=True,
                observed_provider_payload=observed_provider_payload,
            )
    return ProviderChunkProcessingResult(
        emitted_chunks=tuple(emitted_chunks),
        terminal=False,
        observed_provider_payload=observed_provider_payload,
    )
