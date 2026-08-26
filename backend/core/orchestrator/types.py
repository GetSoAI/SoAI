"""SoAI - Orchestrator cross-subsystem types [backend/core/orchestrator/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("MCPToolContext",)


@dataclass(frozen=True, slots=True)
class MCPToolContext:
    conv_id: str
    message_index: int
    user_id: int
    tool_map: dict[str, dict[str, JSONValue]]
    visible_tool_names: tuple[str, ...] | None = None
    tool_approval_required: bool = False
    assistant_at_ms: int | None = None
    assistant_turn_at_ms: int | None = None
    model_variant_index: int | None = None
    user_interaction_timeout_ms: int = DEFAULT_USER_INTERACTION_TIMEOUT_MS
