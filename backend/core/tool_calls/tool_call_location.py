"""SoAI - Shared tool call timeline location [backend/core/tool_calls/tool_call_location.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ToolCallLocation",)


@dataclass(frozen=True, slots=True)
class ToolCallLocation:
    conv_id: str
    message_index: int
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
