"""SoAI - Knowledge attachment count mutation helpers [backend/database/repositories/users/conversation_attachment_knowledge_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_ITEM_STATUSES,
    KNOWLEDGE_ITEM_STATUSES,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "apply_status_count_transition",
    "empty_status_counts",
    "serialize_status_counts",
    "terminal_processing_state_from_counts",
)


def empty_status_counts() -> JSONDict:
    return {}


def serialize_status_counts(status_counts: JSONDict) -> str:
    cleaned: JSONDict = {}
    for key, value in status_counts.items():
        if key not in KNOWLEDGE_ITEM_STATUSES:
            continue
        if not is_strict_int(value) or value <= 0:
            continue
        cleaned[key] = value
    return serialize_json_compact_stable_strict(cleaned)


def apply_status_count_transition(
    status_counts_json: str,
    *,
    previous_status: str | None,
    next_status: str,
) -> JSONDict:
    status_counts = parse_json_dict(status_counts_json, field="status_counts_json")
    if previous_status in KNOWLEDGE_ITEM_STATUSES:
        previous_value = status_counts.get(previous_status)
        previous_count = (
            previous_value
            if not isinstance(previous_value, bool) and isinstance(previous_value, int)
            else 0
        )
        if previous_count <= 1:
            status_counts.pop(previous_status, None)
        else:
            status_counts[previous_status] = previous_count - 1
    if next_status in KNOWLEDGE_ITEM_STATUSES:
        next_value = status_counts.get(next_status)
        next_count = (
            next_value if not isinstance(next_value, bool) and isinstance(next_value, int) else 0
        )
        status_counts[next_status] = next_count + 1
    return status_counts


def terminal_processing_state_from_counts(status_counts: JSONDict) -> str | None:
    active_count = 0
    for status in KNOWLEDGE_ACTIVE_ITEM_STATUSES:
        value = status_counts.get(status)
        if not isinstance(value, bool) and isinstance(value, int) and value > 0:
            active_count += value
    if active_count > 0:
        return None
    completed = _positive_count_or_zero(status_counts, "completed")
    skipped = _positive_count_or_zero(status_counts, "skipped")
    cancelled = _positive_count_or_zero(status_counts, "cancelled")
    errors = _positive_count_or_zero(status_counts, "error")
    terminal_count = completed + skipped + cancelled + errors
    if terminal_count <= 0:
        return None
    if cancelled == terminal_count:
        return "cancelled"
    if errors == terminal_count:
        return "error"
    return "ready"


def _positive_count_or_zero(status_counts: JSONDict, status: str) -> int:
    value = status_counts.get(status)
    if not is_strict_int(value) or value <= 0:
        return 0
    return value
