"""SoAI - Atomic conversation message regeneration admission [backend/database/repositories/users/conversation_input_regeneration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.conversations.settings_authority import resolve_conversation_settings_authority
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_input_active_state_reads import (
    sync_read_active_conversation_input_summary,
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
    read_conversation_input_by_source_key,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_regeneration_targets import (
    resolve_regeneration_cursor_source,
    resolve_regeneration_retry_source,
    sync_next_regeneration_assistant_timestamp,
)
from database.repositories.users.conversation_stream_cancellation_state import (
    sync_has_pending_chat_stream_cancellation,
)
from database.repositories.users.conversation_sync_operations import sync_get_conversation
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_require_expected_conversation_version,
)
from database.repositories.users.message_assistant_mutation_cleanup import (
    delete_auxiliary_for_assistant_rows,
    select_assistant_rows_for_delete,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_input_mutation_fence import (
    require_message_mutation_allowed,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_admit_conversation_regeneration",)


def _format_regeneration_attempt(row: SQLiteRowDict | None) -> JSONDict | None:
    formatted = format_conversation_input_row(row)
    if formatted is None:
        return None
    if formatted.get("regeneration_request") is None:
        raise ConflictError("Conversation input identity belongs to a different command.")
    return formatted


def _attach_replacement_state(
    conn: sqlite3.Connection,
    attempt: JSONDict,
) -> JSONDict:
    request_id = attempt.get("request_id")
    conv_id = attempt.get("conv_id")
    if not isinstance(request_id, str) or not isinstance(conv_id, str):
        raise StateError("Conversation regeneration execution identity is invalid.")
    replacement = conn.execute(
        """
        SELECT 1 FROM webui_messages
        WHERE conv_id = ? AND role = 'assistant'
          AND (request_id = ? OR request_id GLOB ? || ':variant:[0-9]*')
        LIMIT 1
        """,
        (conv_id, request_id, request_id),
    ).fetchone()
    attempt["has_assistant_replacement"] = replacement is not None
    return attempt


def _resolve_existing_attempt(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    source_key: str,
    regeneration_request_json: str,
) -> JSONDict | None:
    existing = read_conversation_input_by_source_key(
        conn,
        user_id=user_id,
        transport_origin="chat",
        source_key=source_key,
    )
    if existing is None:
        return None
    if existing.get("conv_id") != conv_id:
        raise ConflictError("Conversation regeneration identity belongs to another conversation.")
    if existing.get("regeneration_request_json") != regeneration_request_json:
        raise ConflictError("Conversation regeneration identity command conflict.")
    formatted = _format_regeneration_attempt(existing)
    if formatted is None:
        raise StateError("Conversation regeneration attempt is missing after lookup.")
    result = _attach_replacement_state(
        conn,
        attach_conversation_input_dispatch_state(conn, formatted),
    )
    result["regeneration_replayed"] = True
    return result


def _require_idle_execution(conn: sqlite3.Connection, *, conv_id: str, user_id: int) -> None:
    active = sync_read_active_conversation_input_summary(conn, conv_id, user_id)
    if active.has_active_inputs:
        raise ConflictError("Conversation regeneration requires an idle input queue.")
    if sync_has_pending_chat_stream_cancellation(conn, user_id, conv_id):
        raise ConflictError(
            "Conversation regeneration is unavailable while cancellation is pending."
        )
    running_turn = conn.execute(
        """
        SELECT 1 FROM webui_agent_turns
        WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status = 'running'
        LIMIT 1
        """,
        (conv_id, user_id),
    ).fetchone()
    if running_turn is not None:
        raise ConflictError(
            "Conversation regeneration is unavailable while an agent turn is running."
        )


def _require_settings_authority_fresh(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    settings_authority_json: str,
) -> None:
    expected_authority = parse_json_dict(
        settings_authority_json,
        field="settings_authority_json",
    )
    current_conversation = sync_get_conversation(conn, conv_id, user_id)
    if current_conversation is None:
        raise StateError("Conversation disappeared during regeneration admission.")
    current_authority = resolve_conversation_settings_authority(current_conversation).model_settings
    if current_authority != expected_authority:
        raise ConflictError("Conversation settings changed while regeneration was preparing.")


def sync_admit_conversation_regeneration(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    source_key: str,
    client_id: str,
    client_request_id: str,
    regeneration_request_json: str,
    model_settings_json: str,
    settings_authority_json: str,
    input_id: str,
    request_id: str,
    accepted_at_ms: int,
) -> JSONDict:
    ensure_conversation_owned(conn, conv_id, user_id)
    existing = _resolve_existing_attempt(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        source_key=source_key,
        regeneration_request_json=regeneration_request_json,
    )
    if existing is not None:
        return existing
    command = parse_json_dict(regeneration_request_json, field="regeneration_request_json")
    model_settings = parse_json_dict(model_settings_json, field="model_settings_json")
    expected_revision = command.get("expected_last_modified_at_ms")
    if not is_strict_int(expected_revision):
        raise ValidationError("Conversation regeneration expected revision is invalid.")
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=int(expected_revision),
    )
    _require_settings_authority_fresh(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        settings_authority_json=settings_authority_json,
    )
    _require_idle_execution(conn, conv_id=conv_id, user_id=user_id)
    source_message_id: int
    boundary_at_ms: int | None
    boundary_id: int | None
    if command.get("target") is not None:
        source_message_id, boundary_at_ms, boundary_id = resolve_regeneration_cursor_source(
            conn,
            conv_id=conv_id,
            command=command,
        )
    else:
        source_message_id, boundary_at_ms, boundary_id = resolve_regeneration_retry_source(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            command=command,
        )
    assistant_at_ms = sync_next_regeneration_assistant_timestamp(conn, conv_id)
    if boundary_at_ms is not None and boundary_id is not None:
        where_sql = "(created_at_ms > ? OR (created_at_ms = ? AND id >= ?))"
        params = (boundary_at_ms, boundary_at_ms, boundary_id)
        protected_row = conn.execute(
            f"SELECT 1 FROM webui_messages WHERE conv_id = ? AND message_type = 'control' AND {where_sql} LIMIT 1",
            (conv_id, *params),
        ).fetchone()
        if protected_row is not None:
            raise ValidationError("System-owned control messages cannot be regenerated across.")
        require_message_mutation_allowed(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            where_sql=(
                "message.created_at_ms > ? OR " "(message.created_at_ms = ? AND message.id >= ?)"
            ),
            params=params,
        )
        assistant_rows = select_assistant_rows_for_delete(
            conn,
            conv_id=conv_id,
            where_sql=where_sql,
            params=params,
        )
        delete_auxiliary_for_assistant_rows(conn, conv_id=conv_id, assistant_rows=assistant_rows)
        conn.execute(
            f"DELETE FROM webui_messages WHERE conv_id = ? AND {where_sql}",
            (conv_id, *params),
        )
    accepted_revision = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    conversation_generation_row = conn.execute(
        "SELECT input_generation FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()
    if conversation_generation_row is None or not is_strict_int(conversation_generation_row[0]):
        raise StateError("Conversation input generation is invalid.")
    content_fingerprint = build_conversation_input_content_fingerprint(
        input_type="prompt",
        text="",
        attachment_content=[],
        model_settings=model_settings,
        source_metadata={},
        media_descriptors=[],
        regeneration_request=command,
    )
    insert_cursor = conn.execute(
        """
        INSERT INTO webui_conversation_inputs (
            input_id, conv_id, user_id, input_type, transport_origin, text,
            attachment_content_json, model_settings_json, source_key, content_fingerprint,
            client_id, client_request_id, source_metadata_json, media_descriptors_json,
            state, conversation_generation, materialized_message_id,
            materialized_message_at_ms, request_id, assistant_at_ms, assistant_turn_at_ms,
            model_variant_index, accepted_at_ms, updated_at_ms, regeneration_request_json,
            regeneration_accepted_revision
        ) SELECT ?, ?, ?, 'prompt', 'chat', '', '[]', ?, ?, ?, ?, ?, '{}', '[]',
                 'pending', ?, id, created_at_ms, ?, ?, ?, 0, ?, ?, ?, ?
          FROM webui_messages
         WHERE conv_id = ? AND id = ? AND role = 'user'
        """,
        (
            input_id,
            conv_id,
            user_id,
            model_settings_json,
            source_key,
            content_fingerprint,
            client_id,
            client_request_id,
            int(conversation_generation_row[0]),
            request_id,
            assistant_at_ms,
            assistant_at_ms,
            accepted_at_ms,
            accepted_at_ms,
            regeneration_request_json,
            accepted_revision,
            conv_id,
            source_message_id,
        ),
    )
    if insert_cursor.rowcount != 1:
        raise StateError("Conversation regeneration source user message changed during admission.")
    inserted = sync_fetch_one_as_dict(
        conn.execute("SELECT * FROM webui_conversation_inputs WHERE input_id = ?", (input_id,)),
    )
    formatted = _format_regeneration_attempt(inserted)
    if formatted is None:
        raise StateError("Conversation regeneration attempt is missing after admission.")
    formatted["message_count"] = sync_count_stored_messages(conn, conv_id)
    formatted["regeneration_replayed"] = False
    return _attach_replacement_state(
        conn,
        attach_conversation_input_dispatch_state(conn, formatted),
    )
