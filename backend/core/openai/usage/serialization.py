"""SoAI - Canonical OpenAI usage serialization [backend/core/openai/usage/serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.usage.models import CanonicalUsage
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_internal_usage_payload",
    "extract_public_usage_payload",
    "is_aggregate_usage_source",
)


def build_internal_usage_payload(usage: CanonicalUsage) -> JSONDict:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "usage_source": usage.usage_source,
    }


def extract_public_usage_payload(value: JSONValue) -> JSONDict | None:
    payload = coerce_json_dict(value)
    if payload is None:
        return None
    prompt_tokens = coerce_optional_non_negative_int_strict(payload.get("prompt_tokens"))
    completion_tokens = coerce_optional_non_negative_int_strict(payload.get("completion_tokens"))
    total_tokens = coerce_optional_non_negative_int_strict(payload.get("total_tokens"))
    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        return None
    if total_tokens != prompt_tokens + completion_tokens:
        return None
    normalized: JSONDict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    prompt_details = coerce_json_dict(payload.get("prompt_tokens_details"))
    if prompt_details is not None:
        cached_tokens = coerce_optional_non_negative_int_strict(prompt_details.get("cached_tokens"))
        if cached_tokens is not None and cached_tokens <= prompt_tokens:
            normalized["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    return normalized


def is_aggregate_usage_source(value: JSONValue) -> bool:
    usage_source = coerce_optional_trimmed_str(value)
    return usage_source is not None and usage_source.startswith("aggregate_")
