"""SoAI - Stored conversation message builders [backend/core/conversations/stored_message_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.epoch import EPOCH_MS_MIN, require_unix_epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_canonical_assistant_message",)


def build_canonical_assistant_message(
    *,
    content: str,
    timestamp_ms: int,
    model_id: str | None,
    finish_reason: str | None = None,
    assistant_event_timeline: list[JSONDict] | None = None,
) -> JSONDict:
    normalized_timestamp = require_unix_epoch_ms(
        timestamp_ms,
        error_message=f"timestamp_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}.",
        enforce_maximum=False,
    )
    message: JSONDict = {
        "role": "assistant",
        "content": str(content or ""),
        "timestamp": normalized_timestamp,
        "assistant_turn_at_ms": normalized_timestamp,
        "model_variant_index": 0,
        "assistant_event_timeline": list(assistant_event_timeline or []),
    }
    normalized_model_id = str(model_id or "").strip()
    if normalized_model_id:
        message["model_id"] = normalized_model_id
    normalized_finish_reason = str(finish_reason or "").strip()
    if normalized_finish_reason:
        message["finish_reason"] = normalized_finish_reason
    return message
