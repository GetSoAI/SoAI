"""SoAI - Conversation draft revision state [backend/core/conversations/conversation_draft_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ConversationDraftMutationResult", "ConversationDraftState")


@dataclass(frozen=True, slots=True)
class ConversationDraftState:
    draft: JSONDict | None
    revision: int


@dataclass(frozen=True, slots=True)
class ConversationDraftMutationResult:
    state: ConversationDraftState
    applied: bool
