"""SoAI - Conversation message write result model [backend/core/conversations/conversation_message_write_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict

__all__ = ("ConversationMessageWriteResult",)


@dataclass(frozen=True, slots=True)
class ConversationMessageWriteResult:
    last_modified_at_ms: int
    message_count: int
    canonical_messages: list[JSONDict] = field(default_factory=list[JSONDict])
    knowledge_attachment_summaries: list[JSONDict] = field(default_factory=list[JSONDict])
