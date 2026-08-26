"""SoAI - Assistant comparison-turn validation and anchoring [backend/database/repositories/users/message_comparison_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
    require_assistant_turn_variant_invariants,
)
from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.requirements import require_non_negative_int

__all__ = (
    "AssistantToolCallAnchor",
    "build_assistant_tool_call_anchors",
)


@dataclass(frozen=True, slots=True)
class AssistantToolCallAnchor:
    assistant_at_ms: int
    assistant_turn_at_ms: int
    logical_message_index: int
    model_variant_index: int


def validate_assistant_comparison_turns(
    validated_messages: list[ConversationMessageStoragePayload],
) -> None:
    variant_indexes_by_turn: dict[int, set[int]] = {}
    duplicate_variant_indexes_by_turn: dict[int, set[int]] = {}
    canonical_timestamps_by_turn: dict[int, int] = {}
    for validated in validated_messages:
        if validated.get("role") != "assistant":
            continue
        assistant_turn_at_ms = require_unix_epoch_ms(
            validated.get("assistant_turn_at_ms"),
            error_message="Assistant message assistant_turn_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        assistant_at_ms = require_unix_epoch_ms(
            validated.get("created_at_ms"),
            error_message="Assistant message created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        model_variant_index = require_non_negative_int(
            validated.get("model_variant_index"),
            error_message="Assistant message model_variant_index must be an integer.",
        )
        require_assistant_turn_variant_invariants(
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            assistant_turn_after_assistant_error_message=(
                "Assistant message assistant_turn_at_ms must not be greater than created_at_ms."
            ),
            canonical_variant_mismatch_error_message=(
                "Canonical assistant message created_at_ms must equal assistant_turn_at_ms."
            ),
        )
        identity = AssistantTurnVariantIdentity(
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )
        if identity.assistant_turn_at_ms not in variant_indexes_by_turn:
            variant_indexes_by_turn[identity.assistant_turn_at_ms] = set()
            duplicate_variant_indexes_by_turn[identity.assistant_turn_at_ms] = set()
        if identity.model_variant_index in variant_indexes_by_turn[identity.assistant_turn_at_ms]:
            duplicate_variant_indexes_by_turn[identity.assistant_turn_at_ms].add(
                identity.model_variant_index,
            )
        variant_indexes_by_turn[identity.assistant_turn_at_ms].add(identity.model_variant_index)
        if identity.model_variant_index == 0:
            canonical_timestamps_by_turn[identity.assistant_turn_at_ms] = identity.assistant_at_ms
    for assistant_turn_at_ms, variant_indexes in variant_indexes_by_turn.items():
        duplicate_variant_indexes = duplicate_variant_indexes_by_turn[assistant_turn_at_ms]
        if duplicate_variant_indexes:
            raise ValidationError(
                "Assistant comparison turn variant indexes must be unique within a turn.",
            )
        if 0 not in variant_indexes:
            raise ValidationError("Assistant comparison turn must contain canonical variant 0.")
        highest_variant_index = max(variant_indexes)
        expected_variant_indexes = set(range(highest_variant_index + 1))
        if variant_indexes != expected_variant_indexes:
            raise ValidationError(
                "Assistant comparison turn variant indexes must be contiguous starting at 0.",
            )
        if assistant_turn_at_ms not in canonical_timestamps_by_turn:
            raise ValidationError("Assistant comparison turn canonical created_at_ms is missing.")


def build_assistant_tool_call_anchors(
    validated_messages: list[ConversationMessageStoragePayload],
) -> list[AssistantToolCallAnchor]:
    validate_assistant_comparison_turns(validated_messages)
    logical_message_index = 0
    logical_index_by_turn: dict[int, int] = {}
    anchors: list[AssistantToolCallAnchor] = []
    for validated in validated_messages:
        role = validated.get("role")
        if role == "system":
            continue
        if role != "assistant":
            logical_message_index += 1
            continue
        assistant_at_ms = require_unix_epoch_ms(
            validated.get("created_at_ms"),
            error_message="Assistant message created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        assistant_turn_at_ms = require_unix_epoch_ms(
            validated.get("assistant_turn_at_ms"),
            error_message="Assistant message assistant_turn_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        model_variant_index = require_non_negative_int(
            validated.get("model_variant_index"),
            error_message="Assistant message model_variant_index must be an integer.",
        )
        identity = AssistantTurnVariantIdentity(
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )
        if identity.model_variant_index == 0:
            logical_index_by_turn[identity.assistant_turn_at_ms] = logical_message_index
            anchors.append(
                AssistantToolCallAnchor(
                    assistant_at_ms=identity.assistant_at_ms,
                    assistant_turn_at_ms=identity.assistant_turn_at_ms,
                    logical_message_index=logical_message_index,
                    model_variant_index=identity.model_variant_index,
                ),
            )
            logical_message_index += 1
            continue
        resolved_logical_message_index = logical_index_by_turn.get(identity.assistant_turn_at_ms)
        if resolved_logical_message_index is None:
            raise ValidationError(
                "Assistant comparison turn canonical variant must appear before comparison variants.",
            )
        anchors.append(
            AssistantToolCallAnchor(
                assistant_at_ms=identity.assistant_at_ms,
                assistant_turn_at_ms=identity.assistant_turn_at_ms,
                logical_message_index=resolved_logical_message_index,
                model_variant_index=identity.model_variant_index,
            ),
        )
    return anchors
