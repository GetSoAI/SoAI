"""SoAI - Provider Responses SSE frame decoding [backend/core/openai/responses_provider_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.sse_block_decoder import (
    decode_openai_sse_block,
    is_valid_openai_decoded_block,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DecodedResponsesProviderFrame",
    "ResponsesProviderStreamError",
    "decode_responses_provider_frame",
)


class ResponsesProviderStreamError(ValueError): ...


@dataclass(frozen=True, slots=True)
class DecodedResponsesProviderFrame:
    payloads: tuple[JSONDict, ...]
    done_observed: bool


def decode_responses_provider_frame(frame: str) -> DecodedResponsesProviderFrame:
    decoded = decode_openai_sse_block(frame)
    if not is_valid_openai_decoded_block(decoded, allow_responses_events=True):
        raise ResponsesProviderStreamError("Provider returned a malformed Responses SSE frame.")
    if not decoded.data_events:
        raise ResponsesProviderStreamError("Provider returned an empty Responses SSE frame.")
    if len(decoded.data_events) > 1:
        raise ResponsesProviderStreamError("Provider returned multiple Responses SSE events.")
    payloads: list[JSONDict] = []
    done_observed = False
    for data_event in decoded.data_events:
        if data_event.is_done:
            done_observed = True
            continue
        payload = data_event.payload
        if not isinstance(payload, dict):
            raise ResponsesProviderStreamError(
                "Provider returned a non-object Responses SSE payload.",
            )
        event_type_value = payload.get("type")
        event_type = event_type_value if isinstance(event_type_value, str) else ""
        if not event_type.startswith("response.") and not isinstance(payload.get("error"), dict):
            raise ResponsesProviderStreamError("Provider returned a non-Responses SSE payload.")
        payloads.append(dict(payload))
    return DecodedResponsesProviderFrame(payloads=tuple(payloads), done_observed=done_observed)
