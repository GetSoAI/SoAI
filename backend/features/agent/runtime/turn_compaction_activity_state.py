"""SoAI - Auto-compaction tool activity state primitives [backend/features/agent/runtime/turn_compaction_activity_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.messages import resolve_error_message
from core.openai.request_fields import resolve_optional_model_name
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AutoCompactionActivityChronology",
    "AutoCompactionActivityState",
    "build_auto_compaction_call_id",
    "require_auto_compaction_sequence_index",
    "resolve_compaction_model",
    "resolve_terminal_error_message",
)

AUTO_COMPACTION_CALL_ID_PREFIX = "context_compaction:auto:"


@dataclass(frozen=True, slots=True)
class AutoCompactionActivityChronology:
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None

    @classmethod
    def from_values(
        cls,
        *,
        content_index_before: JSONValue,
        thinking_index_before: JSONValue,
        thinking_duration_before_ms: JSONValue,
    ) -> AutoCompactionActivityChronology:
        return cls(
            content_index_before=require_non_negative_int_strict(
                content_index_before,
                error_message="Auto-compaction content_index_before must be non-negative.",
            ),
            thinking_index_before=require_non_negative_int_strict(
                thinking_index_before,
                error_message="Auto-compaction thinking_index_before must be non-negative.",
            ),
            thinking_duration_before_ms=require_optional_non_negative_int_strict(
                thinking_duration_before_ms,
                error_message=("Auto-compaction thinking_duration_before_ms must be non-negative."),
            ),
        )

    @classmethod
    def from_activity(cls, activity: JSONDict) -> AutoCompactionActivityChronology:
        return cls.from_values(
            content_index_before=activity.get("content_index_before"),
            thinking_index_before=activity.get("thinking_index_before"),
            thinking_duration_before_ms=activity.get("thinking_duration_before_ms"),
        )

    @classmethod
    def empty(cls) -> AutoCompactionActivityChronology:
        return cls(
            content_index_before=0,
            thinking_index_before=0,
            thinking_duration_before_ms=None,
        )


@dataclass(frozen=True, slots=True)
class AutoCompactionActivityState:
    call_id: str
    sequence_index: int
    chronology: AutoCompactionActivityChronology
    started_at_ms: int
    started_at_monotonic: float | None


def build_auto_compaction_call_id(
    *,
    turn_id: str,
    iteration_index: int,
    created_sequence: int,
) -> str:
    normalized_turn_id = str(turn_id or "").strip()
    if not normalized_turn_id:
        raise ValidationError("Auto-compaction activity requires a turn_id.")
    return (
        f"{AUTO_COMPACTION_CALL_ID_PREFIX}"
        f"{normalized_turn_id}:{int(iteration_index)}:{int(created_sequence)}"
    )


def require_auto_compaction_sequence_index(persisted_activity: JSONDict) -> int:
    sequence_index_value = persisted_activity.get("sequence_index")
    if (
        isinstance(sequence_index_value, bool)
        or not isinstance(sequence_index_value, int)
        or sequence_index_value < 0
    ):
        raise ValidationError("Auto-compaction activity sequence_index is required.")
    return int(sequence_index_value)


def resolve_compaction_model(base_request_payload: JSONDict) -> str:
    model = resolve_optional_model_name(base_request_payload)
    if model is None:
        raise ValidationError("Auto-compaction requires a resolved model.")
    return model


def resolve_terminal_error_message(exception: BaseException, *, default_message: str) -> str:
    return resolve_error_message(str(exception), default_message=default_message)
