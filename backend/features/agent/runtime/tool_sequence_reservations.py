"""SoAI - Agent tool sequence reservation values [backend/features/agent/runtime/tool_sequence_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = (
    "ToolSequenceIndexReservation",
    "build_incremental_tool_sequence_reservation",
    "build_replayed_tool_sequence_reservation",
)


@dataclass(frozen=True, slots=True)
class ToolSequenceIndexReservation:
    streaming_offset_count: int

    def __post_init__(self) -> None:
        require_non_negative_int_strict(
            self.streaming_offset_count,
            error_message="Tool sequence reservation count must be non-negative.",
        )


def build_replayed_tool_sequence_reservation(
    *,
    next_sequence_index: int,
) -> ToolSequenceIndexReservation:
    streaming_offset_count = require_non_negative_int_strict(
        next_sequence_index,
        error_message="Tool sequence reservation next_sequence_index must be non-negative.",
    )
    return ToolSequenceIndexReservation(streaming_offset_count=streaming_offset_count)


def build_incremental_tool_sequence_reservation(
    *,
    count: int,
) -> ToolSequenceIndexReservation:
    streaming_offset_count = require_non_negative_int_strict(
        count,
        error_message="Tool sequence reservation count must be non-negative.",
    )
    return ToolSequenceIndexReservation(streaming_offset_count=streaming_offset_count)
