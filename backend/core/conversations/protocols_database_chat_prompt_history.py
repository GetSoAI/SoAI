"""SoAI - Chat prompt history database protocol [backend/core/conversations/protocols_database_chat_prompt_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("CHAT_PROMPT_HISTORY_LIMIT", "DatabaseChatPromptHistoryProtocol")

CHAT_PROMPT_HISTORY_LIMIT = 100


class DatabaseChatPromptHistoryProtocol(Protocol):
    async def list_prompts(self, *, user_id: int) -> list[str]: ...

    async def clear(self, *, user_id: int) -> None: ...
