"""SoAI - Owner scoped skill revision events [backend/core/events/types_skills.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.database.mutation_requests import MutationClaim
from core.events.types_base import Event, ReplyableCommand
from core.runtime.request_context import RequestContext

__all__ = ("SkillLibraryChangedEvent", "ConversationSkillsChangedEvent", "MaterializeSkillCommand")


@dataclass(slots=True)
class SkillLibraryChangedEvent(Event):
    user_id: int
    revision: int


@dataclass(slots=True)
class ConversationSkillsChangedEvent(Event):
    user_id: int
    conv_id: str
    revision: int


@dataclass(slots=True)
class MaterializeSkillCommand(ReplyableCommand):
    context: RequestContext
    mutation_claim: MutationClaim
    recovery_requested: bool = False
