"""SoAI - Owner-scoped chat library invalidations [backend/core/events/types_chat_libraries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.events.types_base import Event

__all__ = ("MemoryLibraryChangedEvent", "ChatPresetLibraryChangedEvent")


@dataclass(slots=True)
class MemoryLibraryChangedEvent(Event):
    user_id: int


@dataclass(slots=True)
class ChatPresetLibraryChangedEvent(Event):
    user_id: int
