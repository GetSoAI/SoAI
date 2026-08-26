"""SoAI - Claimed input media attachment transition [backend/database/repositories/users/conversation_input_media_ingestion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.serialization.json import serialize_json_compact_stable
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_pending_queue import (
    sync_queue_pending_attachment_references,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)
from database.repositories.users.conversation_input_transition_resolution import (
    read_conversation_input_by_input_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_attach_ingested_input_media",)


def sync_attach_ingested_input_media(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    expected_media_descriptors: list[JSONDict],
    attachment_content: list[JSONValue],
    updated_at_ms: int,
    storage_root: str | None,
) -> JSONDict:
    stored = read_conversation_input_by_input_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        input_id=input_id,
    )
    current = format_conversation_input_row(stored)
    if current is None:
        raise ConflictError("Conversation input is unavailable for media ingestion.")
    if (
        current.get("state") != "materializing"
        or current.get("claim_generation") != claim_generation
        or current.get("claim_owner") != claim_owner
        or current.get("claim_server_boot_id") != server_boot_id
    ):
        raise ConflictError("Conversation input media claim changed.")
    if current.get("media_descriptors") != expected_media_descriptors:
        raise ConflictError("Conversation input media descriptors changed.")
    existing_content = current.get("attachment_content")
    if not isinstance(existing_content, list):
        raise StateError("Conversation input attachment content is invalid.")
    combined_content = [*existing_content, *attachment_content]
    canonical_content = sync_queue_pending_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_content=combined_content,
        conversation_input_id=input_id,
        updated_at_ms=updated_at_ms,
        storage_root=storage_root,
    )
    updated = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE webui_conversation_inputs
            SET attachment_content_json = ?, media_descriptors_json = '[]', updated_at_ms = ?
            WHERE input_id = ? AND conv_id = ? AND user_id = ?
              AND state = 'materializing' AND claim_generation = ?
              AND claim_owner = ? AND claim_server_boot_id = ?
            RETURNING *
            """,
            (
                serialize_json_compact_stable(canonical_content),
                updated_at_ms,
                input_id,
                conv_id,
                user_id,
                claim_generation,
                claim_owner,
                server_boot_id,
            ),
        ),
    )
    result = format_conversation_input_row(updated)
    if result is None:
        raise ConflictError("Conversation input media claim changed before commit.")
    return result
