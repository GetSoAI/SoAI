"""SoAI - WebUI knowledge attachment state values [backend/core/attachments/knowledge_attachment_states.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "KNOWLEDGE_ACTIVE_ATTACHMENT_STATES",
    "KNOWLEDGE_DRAFT_ATTACHMENT_STATE",
    "KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES",
    "KNOWLEDGE_UNUSED_ATTACHMENT_STATE",
)

KNOWLEDGE_DRAFT_ATTACHMENT_STATE = "draft"
KNOWLEDGE_UNUSED_ATTACHMENT_STATE = "unused"
KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES: frozenset[str] = frozenset(
    (KNOWLEDGE_DRAFT_ATTACHMENT_STATE, "queued"),
)
KNOWLEDGE_ACTIVE_ATTACHMENT_STATES: frozenset[str] = frozenset(
    (KNOWLEDGE_DRAFT_ATTACHMENT_STATE, "queued", "committed"),
)
