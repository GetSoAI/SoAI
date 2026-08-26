"""SoAI - WebUI conversation deletion result records [backend/core/conversations/conversation_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict

__all__ = ("DeletedConversationRecord",)


@dataclass(frozen=True, slots=True)
class DeletedConversationRecord:
    conv_id: str
    linked_knowledge_summaries: tuple[JSONDict, ...] = field(default_factory=tuple)
