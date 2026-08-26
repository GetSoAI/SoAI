"""SoAI - Token quota reservation payload parsing [backend/core/quotas/token_reservation_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.openai.quota_enforcement_constants import STREAMING_QUOTA_CUTOFF_REASON
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

__all__ = (
    "TOKEN_QUOTA_MODE",
    "read_token_quota_prompt_tokens",
    "resolve_streaming_completion_token_limit",
    "resolve_token_quota_reservation",
    "resolve_token_quota_units_for_terminal_failure",
)

TOKEN_QUOTA_MODE = "tokens"


def resolve_token_quota_reservation(value: JSONValue) -> JSONDict | None:
    reservation = coerce_json_dict(value)
    if reservation is None:
        return None
    mode_value = reservation.get("mode")
    mode = mode_value if isinstance(mode_value, str) else "none"
    if mode != TOKEN_QUOTA_MODE:
        return None
    return reservation


def read_token_quota_prompt_tokens(metadata: Mapping[str, JSONValue]) -> int | None:
    prompt_tokens = coerce_optional_non_negative_int_strict(metadata.get("prompt_tokens"))
    if prompt_tokens is not None:
        return prompt_tokens
    quota_value = metadata.get("quota")
    quota_reservation = resolve_token_quota_reservation(quota_value)
    if quota_reservation is None:
        return None
    return coerce_optional_non_negative_int_strict(quota_reservation.get("prompt_tokens"))


def _read_token_quota_estimate_units(reservation: JSONDict) -> int:
    estimate_units = coerce_optional_non_negative_int_strict(reservation.get("estimate_units"))
    return estimate_units if estimate_units is not None else 0


def resolve_streaming_completion_token_limit(
    *,
    quota_reservation: JSONDict,
    prompt_tokens: int | None,
    default_overage_units: int,
) -> int | None:
    reservation = resolve_token_quota_reservation(quota_reservation)
    estimate_units = _read_token_quota_estimate_units(reservation) if reservation is not None else 0
    validated_prompt_tokens = coerce_optional_non_negative_int_strict(prompt_tokens)
    if reservation is None or estimate_units <= 0 or validated_prompt_tokens is None:
        return None
    if estimate_units < validated_prompt_tokens:
        return None
    reserved_completion = estimate_units - validated_prompt_tokens
    if reserved_completion <= 0:
        return None
    overage_value = coerce_optional_non_negative_int_strict(
        reservation.get("streaming_overage_units"),
    )
    overage_units = overage_value if overage_value is not None else max(0, default_overage_units)
    if reservation.get("overage_included_in_estimate") is True:
        return reserved_completion
    return reserved_completion + max(0, overage_units)


def resolve_token_quota_units_for_terminal_failure(
    reservation_value: JSONValue,
    *,
    reason: str,
) -> int:
    reservation = resolve_token_quota_reservation(reservation_value)
    if reservation is None:
        return 0
    estimate_units = _read_token_quota_estimate_units(reservation)
    if estimate_units <= 0:
        return 0
    normalized_reason = str(reason or "").strip()
    if normalized_reason != STREAMING_QUOTA_CUTOFF_REASON:
        return estimate_units
    if reservation.get("overage_included_in_estimate") is True:
        return estimate_units
    overage_units = coerce_optional_non_negative_int_strict(
        reservation.get("streaming_overage_units"),
    )
    return estimate_units + (overage_units if overage_units is not None else 0)
