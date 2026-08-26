"""SoAI - Assistant turn variant identity primitives [backend/core/conversations/assistant_turn_variant_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue
from core.validation.epoch import EPOCH_MS_MIN, require_unix_epoch_ms
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)

__all__ = (
    "AssistantTurnVariantIdentity",
    "require_assistant_turn_variant_identity_epoch_ms",
    "require_assistant_turn_variant_invariants",
    "require_canonical_assistant_turn_identity_epoch_ms",
    "require_chat_stream_start_identity",
)


@dataclass(frozen=True, slots=True)
class AssistantTurnVariantIdentity:
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int


def require_assistant_turn_variant_invariants(
    *,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    assistant_turn_after_assistant_error_message: str,
    canonical_variant_mismatch_error_message: str,
) -> None:
    if assistant_turn_at_ms > assistant_at_ms:
        raise ValidationError(assistant_turn_after_assistant_error_message)
    if model_variant_index == 0 and assistant_turn_at_ms != assistant_at_ms:
        raise ValidationError(canonical_variant_mismatch_error_message)


def require_assistant_turn_variant_identity_epoch_ms(
    *,
    assistant_at_ms: JSONValue,
    assistant_turn_at_ms: JSONValue,
    model_variant_index: JSONValue,
    assistant_at_ms_epoch_error_message: str,
    assistant_turn_at_ms_epoch_error_message: str,
    model_variant_index_error_message: str,
    assistant_turn_after_assistant_error_message: str,
    canonical_variant_mismatch_error_message: str,
) -> AssistantTurnVariantIdentity:
    resolved_assistant_at_ms = require_unix_epoch_ms(
        assistant_at_ms,
        error_message=assistant_at_ms_epoch_error_message,
        enforce_maximum=False,
    )
    resolved_assistant_turn_at_ms = require_unix_epoch_ms(
        assistant_turn_at_ms,
        error_message=assistant_turn_at_ms_epoch_error_message,
        enforce_maximum=False,
    )
    resolved_model_variant_index = require_non_negative_int_strict(
        model_variant_index,
        error_message=model_variant_index_error_message,
    )
    require_assistant_turn_variant_invariants(
        assistant_at_ms=resolved_assistant_at_ms,
        assistant_turn_at_ms=resolved_assistant_turn_at_ms,
        model_variant_index=resolved_model_variant_index,
        assistant_turn_after_assistant_error_message=assistant_turn_after_assistant_error_message,
        canonical_variant_mismatch_error_message=canonical_variant_mismatch_error_message,
    )
    return AssistantTurnVariantIdentity(
        assistant_at_ms=resolved_assistant_at_ms,
        assistant_turn_at_ms=resolved_assistant_turn_at_ms,
        model_variant_index=resolved_model_variant_index,
    )


def require_canonical_assistant_turn_identity_epoch_ms(
    *,
    assistant_at_ms: JSONValue,
    assistant_turn_at_ms: JSONValue,
    payload_label: str,
) -> AssistantTurnVariantIdentity:
    return require_assistant_turn_variant_identity_epoch_ms(
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=0,
        assistant_at_ms_epoch_error_message=(
            f"{payload_label}.assistant_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
        ),
        assistant_turn_at_ms_epoch_error_message=(
            f"{payload_label}.assistant_turn_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
        ),
        model_variant_index_error_message=f"{payload_label} model_variant_index is invalid.",
        assistant_turn_after_assistant_error_message=(
            f"{payload_label}.assistant_turn_at_ms must not be greater than assistant_at_ms."
        ),
        canonical_variant_mismatch_error_message=(
            f"{payload_label} assistant identity must be canonical."
        ),
    )


def require_chat_stream_start_identity(
    *,
    assistant_at_ms: JSONValue,
    assistant_turn_at_ms: JSONValue,
    model_variant_index: JSONValue,
) -> AssistantTurnVariantIdentity:
    resolved_assistant_at_ms = require_positive_int_strict(
        assistant_at_ms,
        error_message="assistant_at_ms must be a positive integer.",
    )
    resolved_assistant_turn_at_ms = require_positive_int_strict(
        assistant_turn_at_ms,
        error_message="assistant_turn_at_ms must be a positive integer.",
    )
    return require_assistant_turn_variant_identity_epoch_ms(
        assistant_at_ms=resolved_assistant_at_ms,
        assistant_turn_at_ms=resolved_assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        assistant_at_ms_epoch_error_message=(
            f"assistant_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
        ),
        assistant_turn_at_ms_epoch_error_message=(
            f"assistant_turn_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
        ),
        model_variant_index_error_message="model_variant_index must be a non-negative integer.",
        assistant_turn_after_assistant_error_message=(
            "assistant_turn_at_ms must not be greater than assistant_at_ms."
        ),
        canonical_variant_mismatch_error_message=(
            "Canonical variant 0 assistant_at_ms must equal assistant_turn_at_ms."
        ),
    )
