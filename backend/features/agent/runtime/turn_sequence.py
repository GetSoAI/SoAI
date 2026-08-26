"""SoAI - Agent turn sequence helpers [backend/features/agent/runtime/turn_sequence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_turn_sequence",
    "create_sequence_counter",
)


def coerce_turn_sequence(turn_record: JSONDict | None) -> int:
    if not isinstance(turn_record, dict):
        return 0
    sequence_value = turn_record.get("sequence")
    if isinstance(sequence_value, bool):
        return 0
    if isinstance(sequence_value, int):
        return max(0, int(sequence_value))
    if isinstance(sequence_value, float):
        return max(0, int(sequence_value))
    if isinstance(sequence_value, str):
        normalized = sequence_value.strip()
        if normalized.isdigit():
            return max(0, int(normalized))
    return 0


def create_sequence_counter(start_sequence: int = 0) -> Callable[[], int]:
    sequence = max(0, int(start_sequence))

    def next_sequence() -> int:
        nonlocal sequence
        sequence += 1
        return sequence

    return next_sequence
