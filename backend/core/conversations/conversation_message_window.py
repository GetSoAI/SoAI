"""SoAI - Conversation message cursor window models [backend/core/conversations/conversation_message_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict

    type ConversationMessageWindowDirection = Literal["tail", "before", "after", "around"]

__all__ = (
    "ConversationMessageCursor",
    "ConversationMessageWindowResult",
    "ConversationRunningActivitySnapshot",
)


@dataclass(frozen=True, slots=True)
class ConversationMessageCursor:
    created_at_ms: int
    id: int


@dataclass(frozen=True, slots=True)
class ConversationMessageWindowResult:
    conv_id: str
    messages: list[JSONDict]
    returned_count: int
    loaded_count_hint: int
    total_count: int
    oldest_cursor: ConversationMessageCursor | None
    newest_cursor: ConversationMessageCursor | None
    has_older: bool
    has_newer: bool
    last_modified_at_ms: int


@dataclass(frozen=True, slots=True)
class ConversationRunningActivitySnapshot:
    conv_id: str
    running_messages: list[JSONDict]
    last_modified_at_ms: int
