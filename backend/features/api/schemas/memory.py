"""SoAI - Memory API schemas [backend/features/api/schemas/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = ("ChatMemoryProfileUpdate",)


class ChatMemoryProfileUpdate(SoAIV1StrictModel):
    preferred_name: str | None = None
    assistant_name: str | None = None
    role_background: str | None = None
    current_goals: str | None = None
    preferences: str | None = None
    dislikes_to_avoid: str | None = None
    communication_style: str | None = None
    recurring_tools_projects: str | None = None
    extra_notes: str | None = None
