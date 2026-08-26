"""SoAI - Conversation input admission transaction [backend/database/repositories/users/conversation_input_sync_enqueue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.chat_prompt_history import (
    build_chat_prompt_history_fingerprint,
    sync_record_chat_prompt,
    sync_verify_chat_prompt_replay,
)
from database.repositories.users.conversation_attachment_pending_queue import (
    sync_queue_pending_attachment_references,
)
from database.repositories.users.conversation_input_claims import (
    attach_conversation_input_dispatch_state,
)
from database.repositories.users.conversation_input_fingerprint import (
    build_conversation_input_content_fingerprint,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)
from database.repositories.users.conversation_input_transition_resolution import (
    read_conversation_input_by_input_id,
    read_conversation_input_by_source_key,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_enqueue_conversation_input",)


def _parse_json_array(raw: str, *, field: str) -> list[JSONValue]:
    parsed = parse_json_value(raw, field=field)
    if not isinstance(parsed, list):
        raise ValidationError(f"{field} must be a JSON array.")
    return parsed


def _parse_json_object(raw: str | None, *, field: str) -> JSONDict | None:
    if raw is None:
        return None
    parsed = parse_json_value(raw, field=field)
    if not isinstance(parsed, dict):
        raise ValidationError(f"{field} must be a JSON object.")
    return parsed


def _require_conversation_generation(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    expected_input_generation: int,
) -> int:
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT input_generation
            FROM webui_conversations
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (conv_id, user_id),
        ),
    )
    if row is None:
        raise ValidationError("Conversation not found.")
    generation = row.get("input_generation")
    if not is_strict_int(generation) or generation < 0:
        raise StateError("Conversation input_generation is invalid.")
    if int(generation) != expected_input_generation:
        raise ConflictError("Conversation generation changed before input admission.")
    return int(generation)


def _resolve_idempotent_input(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    transport_origin: str,
    source_key: str,
    content_fingerprint: str,
    prompt_history_text: str | None,
) -> JSONDict | None:
    existing = read_conversation_input_by_source_key(
        sqlite_conn,
        user_id=user_id,
        transport_origin=transport_origin,
        source_key=source_key,
    )
    if existing is None:
        return None
    if existing.get("conv_id") != conv_id:
        raise ConflictError("Conversation input source key belongs to another conversation.")
    if existing.get("content_fingerprint") != content_fingerprint:
        raise ConflictError("Conversation input source key fingerprint conflict.")
    existing_input_id = existing.get("input_id")
    if not isinstance(existing_input_id, str):
        raise StateError("Conversation input identity is invalid.")
    stored_prompt_history_fingerprint = existing.get("prompt_history_fingerprint")
    if stored_prompt_history_fingerprint is not None and not isinstance(
        stored_prompt_history_fingerprint,
        str,
    ):
        raise StateError("Conversation input prompt history fingerprint is invalid.")
    sync_verify_chat_prompt_replay(
        sqlite_conn,
        source_input_id=existing_input_id,
        expected_text=prompt_history_text,
        stored_fingerprint=stored_prompt_history_fingerprint,
    )
    formatted = format_conversation_input_row(existing)
    if formatted is None:
        raise StateError("Conversation input missing after idempotent lookup.")
    return formatted


def _resolve_target_input_id(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    input_type: str,
) -> str | None:
    if input_type != "steer":
        return None
    row = sqlite_conn.execute(
        """
        SELECT input_id
        FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND input_type IN ('prompt', 'steer')
          AND state IN ('materializing', 'running')
        LIMIT 1
        """,
        (conv_id, user_id),
    ).fetchone()
    if row is None or not isinstance(row[0], str) or not row[0].strip():
        raise ConflictError("Steer input requires an active conversation execution.")
    return row[0].strip()


def sync_enqueue_conversation_input(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    input_type: str,
    transport_origin: str,
    text: str,
    prompt_history_text: str | None,
    attachment_content_json: str,
    model_settings_json: str | None,
    source_key: str,
    client_id: str | None,
    client_request_id: str | None,
    messaging_ingress_id: str | None,
    source_metadata_json: str,
    media_descriptors_json: str,
    input_id: str,
    accepted_at_ms: int,
    expected_input_generation: int,
    storage_root: str | None = None,
) -> JSONDict:
    attachment_content = _parse_json_array(
        attachment_content_json,
        field="attachment_content_json",
    )
    model_settings = _parse_json_object(model_settings_json, field="model_settings_json")
    source_metadata = _parse_json_object(
        source_metadata_json,
        field="source_metadata_json",
    )
    if source_metadata is None:
        raise ValidationError("source_metadata_json is required.")
    media_descriptors = _parse_json_array(
        media_descriptors_json,
        field="media_descriptors_json",
    )
    content_fingerprint = build_conversation_input_content_fingerprint(
        input_type=input_type,
        text=text,
        attachment_content=attachment_content,
        model_settings=model_settings,
        source_metadata=source_metadata,
        media_descriptors=media_descriptors,
    )
    prompt_history_fingerprint = (
        None
        if prompt_history_text is None
        else build_chat_prompt_history_fingerprint(prompt_history_text)
    )
    idempotent = _resolve_idempotent_input(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        transport_origin=transport_origin,
        source_key=source_key,
        content_fingerprint=content_fingerprint,
        prompt_history_text=prompt_history_text,
    )
    if idempotent is not None:
        return attach_conversation_input_dispatch_state(sqlite_conn, idempotent)
    conversation_generation = _require_conversation_generation(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        expected_input_generation=expected_input_generation,
    )
    if attachment_content and transport_origin == "chat" and client_request_id is None:
        raise ValidationError("Attachment-bearing Chat input requires client_request_id.")
    target_input_id = _resolve_target_input_id(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        input_type=input_type,
    )
    sqlite_conn.execute(
        """
        INSERT INTO webui_conversation_inputs (
            input_id, conv_id, user_id, input_type, transport_origin, text,
            attachment_content_json, model_settings_json, source_key, content_fingerprint,
            prompt_history_fingerprint, client_id, client_request_id,
            messaging_ingress_id, source_metadata_json, media_descriptors_json, state,
            conversation_generation, target_input_id, accepted_at_ms, updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (
            input_id,
            conv_id,
            user_id,
            input_type,
            transport_origin,
            text,
            attachment_content_json,
            model_settings_json,
            source_key,
            content_fingerprint,
            prompt_history_fingerprint,
            client_id,
            client_request_id,
            messaging_ingress_id,
            source_metadata_json,
            media_descriptors_json,
            conversation_generation,
            target_input_id,
            accepted_at_ms,
            accepted_at_ms,
        ),
    )
    canonical_attachment_content = sync_queue_pending_attachment_references(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_content=attachment_content,
        conversation_input_id=input_id,
        updated_at_ms=accepted_at_ms,
        storage_root=storage_root,
    )
    canonical_attachment_json = serialize_json_compact_stable(canonical_attachment_content)
    if canonical_attachment_json != attachment_content_json:
        cursor = sqlite_conn.execute(
            """
            UPDATE webui_conversation_inputs
            SET attachment_content_json = ?, updated_at_ms = ?
            WHERE conv_id = ? AND user_id = ? AND input_id = ?
            """,
            (canonical_attachment_json, accepted_at_ms, conv_id, user_id, input_id),
        )
        if cursor.rowcount != 1:
            raise StateError("Conversation input attachment canonicalization failed.")
    if prompt_history_text is not None:
        sync_record_chat_prompt(
            sqlite_conn,
            user_id=user_id,
            source_input_id=input_id,
            text=prompt_history_text,
            accepted_at_ms=accepted_at_ms,
        )
    inserted = read_conversation_input_by_input_id(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        input_id=input_id,
    )
    formatted = format_conversation_input_row(inserted)
    if formatted is None:
        raise StateError("Conversation input missing after insert.")
    return attach_conversation_input_dispatch_state(sqlite_conn, formatted)
