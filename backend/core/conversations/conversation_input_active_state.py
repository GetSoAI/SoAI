"""SoAI - Durable conversation input active state summary [backend/core/conversations/conversation_input_active_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ActiveConversationInputSummary",)


@dataclass(frozen=True, slots=True)
class ActiveConversationInputSummary:
    active_count: int
    head_input_id: str | None
    head_state: str | None
    active_states: tuple[str, ...]

    @property
    def has_active_inputs(self) -> bool:
        return self.active_count > 0
