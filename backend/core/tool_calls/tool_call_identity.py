"""SoAI - Tool call identity value object [backend/core/tool_calls/tool_call_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ToolCallIdentity",)


@dataclass(frozen=True, slots=True)
class ToolCallIdentity:
    conv_id: str
    call_id: str
    assistant_turn_at_ms: int
    model_variant_index: int
    turn_id: str | None
    iteration_index: int | None
    message_index: int | None
