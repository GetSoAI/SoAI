"""SoAI - Tool call live update identity payload fields [backend/core/tool_calls/live_update_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ToolCallLiveUpdateIdentity",)


@dataclass(frozen=True, slots=True)
class ToolCallLiveUpdateIdentity:
    user_id: int
    conv_id: str
    request_id: str | None
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int
