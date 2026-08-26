"""SoAI - Linked knowledge write transactions [backend/database/repositories/users/conversation_linked_knowledge_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.reservation_claims import claim_reserved_write
from core.timing.epoch import epoch_ms
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    map_knowledge_attachment_integrity_error,
)
from database.repositories.users.conversation_linked_knowledge_insertions import (
    insert_linked_knowledge_batch,
)
from database.repositories.users.conversation_linked_knowledge_selection_sync import (
    fetch_active_linked_knowledge_client_batch,
    fetch_canonical_linked_knowledge_items,
    return_matching_linked_knowledge_batch,
    return_matching_linked_knowledge_request_batch,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict

__all__ = ("sync_use_linked_knowledge_items",)


def _use_result(summary: JSONDict, *, idempotent: bool) -> JSONDict:
    return {"summary": summary, "idempotent": idempotent}


def _fetch_inserted_summary(
    conn: sqlite3.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    client_batch_id: str,
) -> JSONDict:
    summary = fetch_active_linked_knowledge_client_batch(
        conn,
        target_conv_id=target_conv_id,
        target_user_id=target_user_id,
        client_batch_id=client_batch_id,
    )
    if summary is None:
        raise StateError("Linked knowledge summary missing after insert.")
    return summary


def sync_use_linked_knowledge_items(
    conn: sqlite3.Connection,
    target_conv_id: str,
    target_user_id: int,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
    client_batch_id: str,
    reservation: DiskSpaceReservationLeaseProtocol,
    reservation_bytes: int,
) -> JSONDict:
    existing = fetch_active_linked_knowledge_client_batch(
        conn,
        target_conv_id=target_conv_id,
        target_user_id=target_user_id,
        client_batch_id=client_batch_id,
    )
    if existing is not None:
        return _use_result(
            return_matching_linked_knowledge_request_batch(
                conn,
                source_conv_id=source_conv_id,
                source_user_id=source_user_id,
                source_knowledge_attachment_id=source_knowledge_attachment_id,
                item_ids=item_ids,
                existing=existing,
            ),
            idempotent=True,
        )
    selected_items = fetch_canonical_linked_knowledge_items(
        conn,
        source_conv_id=source_conv_id,
        source_user_id=source_user_id,
        source_knowledge_attachment_id=source_knowledge_attachment_id,
        item_ids=item_ids,
    )
    try:
        with claim_reserved_write(reservation, size_bytes=reservation_bytes):
            insert_linked_knowledge_batch(
                conn,
                target_conv_id=target_conv_id,
                target_user_id=target_user_id,
                client_batch_id=client_batch_id,
                selected_items=selected_items,
                now_ms=epoch_ms(),
            )
    except sqlite3.IntegrityError as exception:
        existing_after_conflict = fetch_active_linked_knowledge_client_batch(
            conn,
            target_conv_id=target_conv_id,
            target_user_id=target_user_id,
            client_batch_id=client_batch_id,
        )
        if existing_after_conflict is not None:
            return _use_result(
                return_matching_linked_knowledge_batch(
                    conn,
                    selected_items=selected_items,
                    existing=existing_after_conflict,
                ),
                idempotent=True,
            )
        raise map_knowledge_attachment_integrity_error(exception) from exception
    return _use_result(
        _fetch_inserted_summary(
            conn,
            target_conv_id=target_conv_id,
            target_user_id=target_user_id,
            client_batch_id=client_batch_id,
        ),
        idempotent=False,
    )
