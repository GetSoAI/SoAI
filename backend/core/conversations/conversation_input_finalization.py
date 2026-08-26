"""SoAI - Canonical conversation input finalization identity [backend/core/conversations/conversation_input_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ConversationInputFinalization",)


@dataclass(frozen=True, slots=True)
class ConversationInputFinalization:
    input_id: str
    claim_generation: int
    claim_owner: str
    server_boot_id: str
    final_planned_variant: bool
