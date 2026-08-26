"""SoAI - Context compaction boundary state helpers [backend/core/tool_calls/context_compaction_boundary_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.serialization.json import serialize_json_compact_stable_strict
from core.tool_calls.context_compaction_boundary_messages import (
    normalize_context_compaction_boundary_messages,
)
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_context_compaction_boundary_state",
    "context_compaction_boundary_matches",
)

_BOUNDARY_MESSAGE_COUNT_FIELD = "boundary_message_count"
_BOUNDARY_LAST_MESSAGE_TIMESTAMP_FIELD = "boundary_last_message_timestamp"
_BOUNDARY_MESSAGE_DIGEST_FIELD = "boundary_message_digest"


def _resolve_boundary_last_message_timestamp(messages: Sequence[JSONDict]) -> int | None:
    for message in reversed(messages):
        timestamp_value = message.get("timestamp")
        if is_strict_int(timestamp_value):
            return int(timestamp_value)
    return None


def _build_boundary_message_digest(messages: Sequence[JSONDict]) -> str:
    serialized = serialize_json_compact_stable_strict(
        list(messages),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _expected_boundary_state_is_valid(
    *,
    details: JSONDict,
    expected_digest: str,
    expected_count_value: JSONValue,
    expected_timestamp_value: JSONValue,
) -> bool:
    if not expected_digest:
        return False
    if _BOUNDARY_LAST_MESSAGE_TIMESTAMP_FIELD not in details:
        return False
    if not is_strict_int(expected_count_value):
        return False
    if expected_count_value < 0:
        return False
    if isinstance(expected_timestamp_value, bool):
        return False
    return expected_timestamp_value is None or isinstance(expected_timestamp_value, int)


def build_context_compaction_boundary_state(
    messages: Sequence[JSONDict],
    *,
    strip_leading_pinned_prefix: bool = False,
) -> JSONDict:
    normalized_messages = normalize_context_compaction_boundary_messages(
        messages,
        strip_leading_pinned_prefix=strip_leading_pinned_prefix,
    )
    timestamp_source_messages: Sequence[JSONDict]
    if strip_leading_pinned_prefix:
        timestamp_source_messages = split_leading_pinned_prefix(messages)[1]
    else:
        timestamp_source_messages = messages
    return {
        _BOUNDARY_MESSAGE_COUNT_FIELD: len(normalized_messages),
        _BOUNDARY_LAST_MESSAGE_TIMESTAMP_FIELD: _resolve_boundary_last_message_timestamp(
            timestamp_source_messages,
        ),
        _BOUNDARY_MESSAGE_DIGEST_FIELD: _build_boundary_message_digest(normalized_messages),
    }


def context_compaction_boundary_matches(
    messages: Sequence[JSONDict],
    details: JSONDict | None,
    *,
    strip_leading_pinned_prefix: bool = False,
) -> bool:
    if details is None:
        return False
    expected_digest_value = details.get(_BOUNDARY_MESSAGE_DIGEST_FIELD)
    expected_digest = (
        expected_digest_value.strip()
        if isinstance(expected_digest_value, str) and expected_digest_value.strip()
        else ""
    )
    expected_count_value = details.get(_BOUNDARY_MESSAGE_COUNT_FIELD)
    expected_timestamp_value = details.get(_BOUNDARY_LAST_MESSAGE_TIMESTAMP_FIELD)
    if not _expected_boundary_state_is_valid(
        details=details,
        expected_digest=expected_digest,
        expected_count_value=expected_count_value,
        expected_timestamp_value=expected_timestamp_value,
    ):
        return False
    actual_state = build_context_compaction_boundary_state(
        messages,
        strip_leading_pinned_prefix=strip_leading_pinned_prefix,
    )
    actual_count_value = actual_state.get(_BOUNDARY_MESSAGE_COUNT_FIELD)
    actual_digest_value = actual_state.get(_BOUNDARY_MESSAGE_DIGEST_FIELD)
    actual_timestamp_value = actual_state.get(_BOUNDARY_LAST_MESSAGE_TIMESTAMP_FIELD)
    return (
        actual_count_value == expected_count_value
        and actual_digest_value == expected_digest
        and (expected_timestamp_value is None or actual_timestamp_value == expected_timestamp_value)
    )
