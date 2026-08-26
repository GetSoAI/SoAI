"""SoAI - Canonical assistant message identification helpers [backend/core/conversations/canonical_assistant_message.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "is_canonical_assistant_message",
    "resolve_latest_previous_canonical_assistant_message",
)


def is_canonical_assistant_message(message: JSONDict) -> bool:
    if message.get("role") != "assistant":
        return False
    timestamp_value = message.get("timestamp")
    if not is_unix_epoch_ms(timestamp_value, enforce_maximum=False):
        return False
    assistant_turn_value = message.get("assistant_turn_at_ms")
    if not is_unix_epoch_ms(assistant_turn_value, enforce_maximum=False):
        return False
    model_variant_index = message.get("model_variant_index")
    if not is_strict_int(model_variant_index):
        return False
    if model_variant_index != 0:
        return False
    return int(timestamp_value) == int(assistant_turn_value)


def resolve_latest_previous_canonical_assistant_message(
    messages: Iterable[JSONDict],
    *,
    before_timestamp_exclusive: int,
) -> JSONDict | None:
    ordered = list(messages)
    for message in reversed(ordered):
        if not is_canonical_assistant_message(message):
            continue
        timestamp_value = message.get("timestamp")
        if not is_strict_int(timestamp_value):
            continue
        if timestamp_value >= before_timestamp_exclusive:
            continue
        return message
    return None
