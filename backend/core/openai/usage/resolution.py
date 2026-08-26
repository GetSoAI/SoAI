"""SoAI - Canonical OpenAI usage resolution [backend/core/openai/usage/resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.usage.models import (
    CanonicalUsage,
    CanonicalUsageResolution,
    ProviderUsageNormalization,
)
from core.openai.usage.transcript_completion_token_estimation import (
    estimate_transcript_completion_tokens,
)
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.openai.protocols_usage import CompletionTokenTranscriptProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.openai.usage.models import CanonicalUsageSource, ProviderUsageStatus
    from core.types.json import JSONValue

__all__ = (
    "aggregate_canonical_usage",
    "normalize_provider_usage",
    "reconstruct_transcript_usage",
    "resolve_canonical_usage",
)


def normalize_provider_usage(
    *,
    usage_payload: JSONValue,
    prompt_tokens_hint: int | None,
) -> ProviderUsageNormalization:
    if usage_payload is None:
        return ProviderUsageNormalization(usage=None, status="absent")
    if not isinstance(usage_payload, dict):
        return ProviderUsageNormalization(usage=None, status="invalid")
    prompt_tokens, prompt_status = _resolve_usage_counter(
        usage_payload,
        primary_field="prompt_tokens",
        alias_field="input_tokens",
    )
    completion_tokens, completion_status = _resolve_usage_counter(
        usage_payload,
        primary_field="completion_tokens",
        alias_field="output_tokens",
    )
    total_tokens, total_status = _resolve_usage_counter(
        usage_payload,
        primary_field="total_tokens",
        alias_field=None,
    )
    field_statuses = (prompt_status, completion_status, total_status)
    if "invalid" in field_statuses:
        return ProviderUsageNormalization(usage=None, status="invalid")
    if prompt_tokens is None:
        prompt_tokens = coerce_optional_non_negative_int_strict(prompt_tokens_hint)
        if prompt_tokens_hint is not None and prompt_tokens is None:
            return ProviderUsageNormalization(usage=None, status="invalid")
    if prompt_tokens is None or completion_tokens is None:
        return ProviderUsageNormalization(usage=None, status="incomplete")
    resolved_total_tokens = prompt_tokens + completion_tokens
    if total_tokens is not None and total_tokens != resolved_total_tokens:
        return ProviderUsageNormalization(usage=None, status="total_mismatch")
    return ProviderUsageNormalization(
        usage=CanonicalUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=resolved_total_tokens,
            usage_source="provider_reported",
        ),
        status="accepted",
    )


def _resolve_usage_counter(
    usage_payload: dict[str, JSONValue],
    *,
    primary_field: str,
    alias_field: str | None,
) -> tuple[int | None, ProviderUsageStatus]:
    fields = (primary_field,) if alias_field is None else (primary_field, alias_field)
    present_values: list[int] = []
    for field in fields:
        if field not in usage_payload:
            continue
        value = coerce_optional_non_negative_int_strict(usage_payload.get(field))
        if value is None:
            return (None, "invalid")
        present_values.append(value)
    if not present_values:
        return (None, "absent")
    resolved_value = present_values[0]
    if any(value != resolved_value for value in present_values[1:]):
        return (None, "invalid")
    return (resolved_value, "accepted")


def reconstruct_transcript_usage(
    *,
    transcript: CompletionTokenTranscriptProtocol,
    prompt_tokens_hint: int | None,
    prompt_token_counter: PromptTokenCounter,
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> CanonicalUsage:
    prompt_tokens = coerce_optional_non_negative_int_strict(prompt_tokens_hint)
    if prompt_tokens is None:
        raise ValidationError("Prompt tokens are required to reconstruct streaming usage.")
    completion_tokens = estimate_transcript_completion_tokens(
        transcript=transcript,
        prompt_token_counter=prompt_token_counter,
        model_name=model_name,
        token_estimation_profile=token_estimation_profile,
    )
    return CanonicalUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        usage_source="reconstructed_transcript",
    )


def resolve_canonical_usage(
    *,
    transcript: CompletionTokenTranscriptProtocol,
    explicit_usage_payload: JSONValue,
    prompt_tokens_hint: int | None,
    prompt_token_counter: PromptTokenCounter,
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> CanonicalUsageResolution:
    provider_usage = normalize_provider_usage(
        usage_payload=explicit_usage_payload,
        prompt_tokens_hint=prompt_tokens_hint,
    )
    if provider_usage.usage is not None:
        return CanonicalUsageResolution(
            usage=provider_usage.usage,
            status=provider_usage.status,
        )
    reconstructed_usage = reconstruct_transcript_usage(
        transcript=transcript,
        prompt_tokens_hint=prompt_tokens_hint,
        prompt_token_counter=prompt_token_counter,
        model_name=model_name,
        token_estimation_profile=token_estimation_profile,
    )
    return CanonicalUsageResolution(
        usage=reconstructed_usage,
        status=provider_usage.status,
    )


def aggregate_canonical_usage(
    base: CanonicalUsage | None,
    incoming: CanonicalUsage | None,
) -> CanonicalUsage | None:
    if base is None:
        return incoming
    if incoming is None:
        return base
    aggregate_source: CanonicalUsageSource = "aggregate_mixed"
    if base.usage_source in {
        "provider_reported",
        "aggregate_provider_reported",
    } and incoming.usage_source in {"provider_reported", "aggregate_provider_reported"}:
        aggregate_source = "aggregate_provider_reported"
    elif base.usage_source in {
        "reconstructed_transcript",
        "aggregate_reconstructed_transcript",
    } and incoming.usage_source in {
        "reconstructed_transcript",
        "aggregate_reconstructed_transcript",
    }:
        aggregate_source = "aggregate_reconstructed_transcript"
    return CanonicalUsage(
        prompt_tokens=base.prompt_tokens + incoming.prompt_tokens,
        completion_tokens=base.completion_tokens + incoming.completion_tokens,
        total_tokens=base.total_tokens + incoming.total_tokens,
        usage_source=aggregate_source,
    )
