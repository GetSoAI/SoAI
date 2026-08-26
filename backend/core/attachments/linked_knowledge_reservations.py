"""SoAI - Linked knowledge disk reservation sizing [backend/core/attachments/linked_knowledge_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("estimate_linked_knowledge_reservation_bytes",)

_LINKED_KNOWLEDGE_RESERVATION_FLOOR_BYTES = 1_048_576
_LINKED_KNOWLEDGE_SQLITE_MULTIPLIER = 4
_LINKED_KNOWLEDGE_PER_ITEM_BYTES = 8_192


def estimate_linked_knowledge_reservation_bytes(
    *,
    target_conv_id: str,
    target_user_id: int,
    source_conv_id: str,
    source_knowledge_attachment_id: str,
    client_batch_id: str,
    selected_items: list[JSONDict],
) -> int:
    payload: JSONDict = {
        "target_conv_id": target_conv_id,
        "target_user_id": target_user_id,
        "source_conv_id": source_conv_id,
        "source_knowledge_attachment_id": source_knowledge_attachment_id,
        "client_batch_id": client_batch_id,
        "selected_items": selected_items,
    }
    serialized_payload_bytes = len(serialize_json_compact_stable_strict(payload).encode("utf-8"))
    estimated_bytes = (
        serialized_payload_bytes * _LINKED_KNOWLEDGE_SQLITE_MULTIPLIER
        + len(selected_items) * _LINKED_KNOWLEDGE_PER_ITEM_BYTES
    )
    return max(_LINKED_KNOWLEDGE_RESERVATION_FLOOR_BYTES, estimated_bytes)
