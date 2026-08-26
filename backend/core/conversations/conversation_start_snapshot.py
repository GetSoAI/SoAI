"""SoAI - WebUI conversation start snapshot contract [backend/core/conversations/conversation_start_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ConversationStartSnapshot",)


@dataclass(frozen=True, slots=True)
class ConversationStartSnapshot:
    message_count: int
    latest_message_timestamp: int | None
    persisted_messages: list[JSONDict]
    canonical_history: list[JSONDict]
