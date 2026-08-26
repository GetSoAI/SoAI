"""SoAI - Linked knowledge canonical state signature producer [backend/database/repositories/users/conversation_linked_knowledge_signature.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("MISSING_SOURCE_REASON", "linked_state_signature")

MISSING_SOURCE_REASON = "source_document_unavailable"


def linked_state_signature(
    *,
    active_count: int,
    unavailable_count: int,
    child_states: list[JSONDict],
) -> str:
    return serialize_json_compact_stable(
        {
            "active_count": active_count,
            "unavailable_count": unavailable_count,
            "reason": MISSING_SOURCE_REASON if unavailable_count > 0 else None,
            "children": child_states,
        },
    )
