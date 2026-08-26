"""SoAI - OpenAI token quota estimate helpers [backend/features/api/runtime/token_quota_estimates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "QuotaTokenReservationEstimate",
    "build_quota_token_reservation_estimate",
    "enrich_token_quota_reservation",
    "estimate_completion_reservation_tokens",
)


@dataclass(frozen=True, slots=True)
class QuotaTokenReservationEstimate:
    estimate_units: int
    completion_tokens: int
    prompt_tokens: int
    streaming_overage_units: int
    overage_included_in_estimate: bool


def build_quota_token_reservation_estimate(
    config: ConfigProtocol,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    is_streaming: bool,
) -> QuotaTokenReservationEstimate:
    validated_prompt_tokens = require_non_negative_int_strict(
        prompt_tokens,
        error_message="Prompt token reservation estimate must be a non-negative integer.",
    )
    validated_completion_tokens = require_non_negative_int_strict(
        completion_tokens,
        error_message="Completion token reservation estimate must be a non-negative integer.",
    )
    if not isinstance(is_streaming, bool):
        raise ValidationError("Streaming token reservation state must be a boolean.")
    overage = int(config.get_int("API.OPENAI.KEY_QUOTAS.STREAMING_OVERAGE_TOKENS"))
    overage = max(0, int(overage))
    reserved_overage = int(overage) if is_streaming else 0
    estimate_units = max(
        0,
        int(validated_prompt_tokens) + int(validated_completion_tokens) + int(reserved_overage),
    )
    min_units = int(config.get_int("API.OPENAI.KEY_QUOTAS.MIN_TOKEN_RESERVATION_UNITS"))
    min_units = max(0, int(min_units))
    if estimate_units <= 0:
        estimate_units = max(0, int(min_units))
    return QuotaTokenReservationEstimate(
        estimate_units=estimate_units,
        completion_tokens=validated_completion_tokens,
        prompt_tokens=validated_prompt_tokens,
        streaming_overage_units=int(overage),
        overage_included_in_estimate=reserved_overage > 0,
    )


def enrich_token_quota_reservation(
    reservation: JSONDict,
    *,
    estimate: QuotaTokenReservationEstimate,
) -> JSONDict:
    enriched = dict(reservation)
    enriched["streaming_overage_units"] = int(estimate.streaming_overage_units)
    if estimate.overage_included_in_estimate:
        enriched["overage_included_in_estimate"] = True
    enriched["prompt_tokens"] = int(estimate.prompt_tokens)
    return enriched


def estimate_completion_reservation_tokens(
    request_json: dict[str, JSONValue],
    config: ConfigProtocol,
) -> int:
    max_value = int(config.get_int("API.OPENAI.KEY_QUOTAS.MAX_COMPLETION_RESERVATION_TOKENS"))
    if max_value <= 0:
        max_value = 1
    max_candidate = request_json.get("max_output_tokens")
    if is_strict_int(max_candidate) and max_candidate > 0:
        base = int(max_candidate)
    else:
        max_completion_candidate = request_json.get("max_completion_tokens")
        if is_strict_int(max_completion_candidate) and max_completion_candidate > 0:
            base = int(max_completion_candidate)
        else:
            max_tokens_candidate = request_json.get("max_tokens")
            if is_strict_int(max_tokens_candidate) and max_tokens_candidate > 0:
                base = int(max_tokens_candidate)
            else:
                default_value = int(
                    config.get_int("API.OPENAI.KEY_QUOTAS.DEFAULT_COMPLETION_RESERVATION_TOKENS"),
                )
                if default_value <= 0:
                    default_value = 1
                base = int(default_value)
    base = max(1, min(int(base), int(max_value)))
    n_value = request_json.get("n")
    completion_count = int(n_value) if is_strict_int(n_value) and n_value > 0 else 1
    best_of_value = request_json.get("best_of")
    best_of = int(best_of_value) if is_strict_int(best_of_value) and best_of_value > 0 else 1
    fanout = max(1, int(completion_count), int(best_of))
    estimated = int(base) * int(fanout)
    return max(1, min(int(estimated), int(max_value) * int(fanout)))
