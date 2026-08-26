"""SoAI - Canonical OpenAI inference payload normalization [backend/core/openai/inference_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.capability_requirements import augment_openai_capability_requirements
from core.openai.payload_validation import (
    normalize_inference_payload_messages,
    sanitize_openai_request_messages,
)
from core.openai.request_field_filtering import build_inference_request_payload
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "NormalizedOpenAIInferencePayload",
    "normalize_openai_inference_payload",
    "normalize_openai_inference_payload_triple",
)


@dataclass(frozen=True, slots=True)
class NormalizedOpenAIInferencePayload:
    payload: JSONDict
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]


def normalize_openai_inference_payload(
    request_json: JSONDict,
    *,
    logger: LoggerProtocol | None,
    trace_id: str | None,
    base_capabilities: tuple[str, ...] = (),
    filter_request_fields: bool = True,
) -> NormalizedOpenAIInferencePayload:
    working_payload = dict(request_json)
    if filter_request_fields:
        working_payload = build_inference_request_payload(working_payload)
    normalized_messages = normalize_inference_payload_messages(working_payload)
    sanitized = sanitize_openai_request_messages(
        normalized_messages,
        logger=logger,
        trace_id=trace_id,
    )
    required_capabilities, required_modalities = augment_openai_capability_requirements(
        tuple(base_capabilities or ()),
        sanitized,
    )
    return NormalizedOpenAIInferencePayload(
        payload=sanitized,
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
    )


def normalize_openai_inference_payload_triple(
    request_json: JSONDict,
    *,
    logger: LoggerProtocol | None,
    trace_id: str | None,
    base_capabilities: tuple[str, ...] = (),
    filter_request_fields: bool = True,
) -> tuple[JSONDict, tuple[str, ...], tuple[str, ...]]:
    normalized = normalize_openai_inference_payload(
        request_json,
        logger=logger,
        trace_id=trace_id,
        base_capabilities=base_capabilities,
        filter_request_fields=filter_request_fields,
    )
    return (
        normalized.payload,
        normalized.required_capabilities,
        normalized.required_modalities,
    )
