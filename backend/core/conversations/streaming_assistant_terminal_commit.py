"""SoAI - Atomic streaming assistant terminal commit request [backend/core/conversations/streaming_assistant_terminal_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.conversations.assistant_terminal_finalization import (
    TerminalAssistantMessageFinalization,
)
from core.conversations.conversation_input_finalization import ConversationInputFinalization
from core.types.json import JSONDict

__all__ = ("StreamingAssistantTerminalCommitRequest",)


@dataclass(frozen=True, slots=True)
class StreamingAssistantTerminalCommitRequest:
    conv_id: str
    user_id: int
    assistant_at_ms: int
    request_id: str | None
    content_text: str
    events: tuple[tuple[int, int, str, JSONDict, int], ...]
    finalization: TerminalAssistantMessageFinalization
    input_finalization: ConversationInputFinalization | None
