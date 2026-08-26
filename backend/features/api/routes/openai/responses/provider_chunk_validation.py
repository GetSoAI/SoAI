"""SoAI - Strict Responses provider chunk validation [backend/features/api/routes/openai/responses/provider_chunk_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.openai.response_terminal_policy import is_terminal_response_payload
from core.openai.responses_provider_events import (
    ResponsesProviderStreamError,
    decode_responses_provider_frame,
)
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.types.json import JSONDict

__all__ = ("ValidatedResponsesProviderChunk", "validate_responses_provider_chunk")


@dataclass(frozen=True, slots=True)
class ValidatedResponsesProviderChunk:
    payloads: tuple[JSONDict, ...]
    terminal_observed: bool


def validate_responses_provider_chunk(
    accumulator: OpenAISSEFrameAccumulator,
    chunk: bytes,
    *,
    terminal_observed: bool,
) -> ValidatedResponsesProviderChunk:
    decoded_payloads: list[JSONDict] = []
    done_observed = False
    for frame in accumulator.feed(chunk):
        decoded_frame = decode_responses_provider_frame(frame)
        for payload in decoded_frame.payloads:
            if terminal_observed or done_observed:
                raise ResponsesProviderStreamError(
                    "Responses provider emitted a payload after the terminal event."
                )
            event_payload = dict(payload)
            if is_terminal_response_payload(event_payload):
                if not isinstance(event_payload.get("response"), dict):
                    raise ResponsesProviderStreamError(
                        "Provider returned a malformed terminal Responses event."
                    )
                terminal_observed = True
            decoded_payloads.append(event_payload)
        if decoded_frame.done_observed:
            if not terminal_observed:
                raise ResponsesProviderStreamError(
                    "Provider ended the Responses stream without a terminal response event."
                )
            done_observed = True
    if terminal_observed and accumulator.pending_byte_count() > 0:
        raise ResponsesProviderStreamError(
            "Responses provider emitted bytes after the terminal event."
        )
    return ValidatedResponsesProviderChunk(tuple(decoded_payloads), terminal_observed)
