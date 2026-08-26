"""SoAI - Context compaction output message counters [backend/features/agent/runtime/context_compaction/message_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.truncation import SOAI_TRUNCATION_MARKER_TEXT

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_auto_compaction_message_counts",)


def resolve_auto_compaction_message_counts(compacted_messages: list[JSONDict]) -> tuple[int, int]:
    tool_stub_count = 0
    truncated_message_count = 0
    for message in compacted_messages:
        content_value = message.get("content")
        if not isinstance(content_value, str):
            continue
        if SOAI_TRUNCATION_MARKER_TEXT in content_value:
            truncated_message_count += 1
        if message.get("role") == "tool" and "__soai_compaction__" in content_value:
            tool_stub_count += 1
    return (tool_stub_count, truncated_message_count)
