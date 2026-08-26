"""SoAI - Current tool call context tracking [backend/core/tool_calls/current_tool_call.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.tool_calls.tool_call_location import ToolCallLocation

__all__ = ("CurrentToolCallIdentity",)


@dataclass(frozen=True, slots=True)
class CurrentToolCallIdentity(ToolCallLocation):
    user_id: int
    turn_id: str | None
    iteration_index: int | None
    storage_call_id: str
    call_id: str
    tool_name: str = "unknown"
