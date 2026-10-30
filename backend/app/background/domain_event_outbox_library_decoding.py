"""SoAI - Chat library outbox event decoding [backend/app/background/domain_event_outbox_library_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.background.outbox_payload_parsing import coerce_outbox_int, coerce_outbox_str
from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_chat_libraries import (
    ChatPresetLibraryChangedEvent,
    MemoryLibraryChangedEvent,
)
from core.events.types_skills import ConversationSkillsChangedEvent, SkillLibraryChangedEvent
from core.skills.selection import require_skill_revision
from core.types.json import JSONDict

__all__ = ("decode_library_outbox_event",)


def decode_library_outbox_event(
    decoded: JSONDict, event_type: str, event_id: str, timestamp: float
) -> Event:
    user_id = coerce_outbox_int(decoded.get("user_id"), label="user_id")
    if user_id <= 0:
        raise ValidationError("Library event owner must be positive.")
    if event_type == "MemoryLibraryChangedEvent":
        return MemoryLibraryChangedEvent(user_id=user_id, event_id=event_id, timestamp=timestamp)
    if event_type == "ChatPresetLibraryChangedEvent":
        return ChatPresetLibraryChangedEvent(
            user_id=user_id, event_id=event_id, timestamp=timestamp
        )
    revision = require_skill_revision(decoded.get("revision"))
    if event_type == "SkillLibraryChangedEvent":
        return SkillLibraryChangedEvent(
            user_id=user_id, revision=revision, event_id=event_id, timestamp=timestamp
        )
    if event_type == "ConversationSkillsChangedEvent":
        return ConversationSkillsChangedEvent(
            user_id=user_id,
            revision=revision,
            conv_id=coerce_outbox_str(decoded.get("conv_id"), label="conv_id"),
            event_id=event_id,
            timestamp=timestamp,
        )
    raise ValidationError(f"Unsupported library event_type: {event_type}")
