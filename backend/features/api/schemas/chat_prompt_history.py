"""SoAI - Chat prompt history API schemas [backend/features/api/schemas/chat_prompt_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field

from core.conversations.protocols_database_chat_prompt_history import (
    CHAT_PROMPT_HISTORY_LIMIT,
)
from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = ("ChatPromptHistoryResponse",)


class ChatPromptHistoryResponse(SoAIV1StrictModel):
    prompts: list[str] = Field(..., max_length=CHAT_PROMPT_HISTORY_LIMIT)
