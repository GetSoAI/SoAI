"""SoAI - Context compaction message replacement [backend/features/agent/runtime/context_compaction/message_replacement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.truncation import SOAI_TRUNCATION_MARKER_TEXT

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("replace_message_content_with_truncation_stub",)


def replace_message_content_with_truncation_stub(
    *,
    message_history: list[JSONDict],
    message_index: int,
) -> list[JSONDict]:
    if message_index < 0 or message_index >= len(message_history):
        return message_history
    updated_history: list[JSONDict] = [dict(message) for message in message_history]
    target_message = dict(updated_history[message_index])
    target_message["content"] = SOAI_TRUNCATION_MARKER_TEXT
    if "tool_calls" in target_message:
        target_message["tool_calls"] = []
    updated_history[message_index] = target_message
    return updated_history
