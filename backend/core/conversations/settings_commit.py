"""SoAI - Conversation settings commit result contract [backend/core/conversations/settings_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.types.json import JSONDict

__all__ = (
    "ConversationSettingsCommitResult",
    "ConversationToolDefaultsCommitResult",
)


@dataclass(frozen=True, slots=True)
class ConversationSettingsCommitResult:
    conversation: JSONDict
    conversation_changed: bool


@dataclass(frozen=True, slots=True)
class ConversationToolDefaultsCommitResult:
    status: Literal["updated", "unchanged", "superseded", "not_found"]
