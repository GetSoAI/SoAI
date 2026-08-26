"""SoAI - Atomic forced steer batching [backend/database/repositories/users/conversation_input_force_steering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_all_as_dicts, sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_pending_sync import (
    sync_rebind_pending_attachment_references,
)
from database.repositories.users.conversation_input_constants import (
    CONVERSATION_INPUT_DISPATCH_RANK_SQL,
)
from database.repositories.users.conversation_input_fingerprint import (
    build_conversation_input_content_fingerprint,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_force_pending_conversation_steers",)

FORCED_DISPATCH_MODE = "forced_after_interrupt"
FORCED_TERMINAL_CODE = "batched_into_forced_steer"


def _no_forced_input_result() -> JSONDict:
    return {"forced": False, "created": False, "input": None, "source_input_ids": []}


def _read_executing_input(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    request_id: str | None,
    agent_turn_id: str | None,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT * FROM webui_conversation_inputs
            WHERE conv_id = ? AND user_id = ?
              AND state IN ('materializing', 'running', 'input_required')
              AND ((? IS NOT NULL AND (request_id = ? OR ? GLOB request_id || ':variant:[0-9]*'))
                   OR (? IS NOT NULL AND agent_turn_id = ?))
            LIMIT 1
            """,
            (conv_id, user_id, request_id, request_id, request_id, agent_turn_id, agent_turn_id),
        ),
    )


def _read_pending_steers(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    conversation_generation: int,
) -> list[JSONDict]:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"""
            SELECT *, {CONVERSATION_INPUT_DISPATCH_RANK_SQL} AS dispatch_rank
            FROM webui_conversation_inputs
            WHERE conv_id = ? AND user_id = ?
              AND conversation_generation = ?
              AND input_type = 'steer' AND state = 'pending'
            ORDER BY dispatch_rank ASC, accepted_at_ms ASC, id ASC
            """,
            (conv_id, user_id, conversation_generation),
        ),
    )
    formatted: list[JSONDict] = []
    for row in rows:
        input_record = format_conversation_input_row(row)
        if input_record is None:
            raise StateError("Pending steer input is unavailable.")
        formatted.append(input_record)
    return formatted


def _resolve_settings_source_input_id(
    conn: sqlite3.Connection,
    input_id: str,
) -> str:
    row = conn.execute(
        """
        WITH RECURSIVE lineage(input_id, target_input_id, model_settings_json) AS (
            SELECT input_id, target_input_id, model_settings_json
            FROM webui_conversation_inputs WHERE input_id = ?
            UNION
            SELECT parent.input_id, parent.target_input_id, parent.model_settings_json
            FROM webui_conversation_inputs AS parent
            JOIN lineage ON parent.input_id = lineage.target_input_id
        )
        SELECT input_id FROM lineage
        WHERE model_settings_json IS NOT NULL
        LIMIT 1
        """,
        (input_id,),
    ).fetchone()
    if row is None or not isinstance(row[0], str) or not row[0].strip():
        raise StateError("Forced steer input settings source is unavailable.")
    return row[0].strip()


def _combine_steer_content(
    steers: list[JSONDict],
) -> tuple[str, list[JSONValue], list[JSONValue], list[str]]:
    texts: list[str] = []
    attachment_content: list[JSONValue] = []
    media_descriptors: list[JSONValue] = []
    source_input_ids: list[str] = []
    for steer in steers:
        text = steer.get("text")
        attachments = steer.get("attachment_content")
        media = steer.get("media_descriptors")
        input_id = steer.get("input_id")
        if not isinstance(text, str) or not isinstance(attachments, list):
            raise StateError("Pending steer content is invalid.")
        if not isinstance(media, list) or not isinstance(input_id, str) or not input_id.strip():
            raise StateError("Pending steer identity is invalid.")
        if text.strip():
            texts.append(text.strip())
        attachment_content.extend(attachments)
        for descriptor in media:
            if not isinstance(descriptor, dict):
                raise StateError("Pending steer media descriptor is invalid.")
            media_descriptors.append(descriptor)
        source_input_ids.append(input_id.strip())
    return "\n".join(texts), attachment_content, media_descriptors, source_input_ids


def _insert_forced_input(
    conn: sqlite3.Connection,
    *,
    executing: JSONDict,
    steers: list[JSONDict],
) -> tuple[JSONDict, list[str]]:
    text, attachments, media_descriptors, source_input_ids = _combine_steer_content(steers)
    input_id = create_prefixed_hex_id("cinput", length=16)
    client_request_id = create_prefixed_hex_id("forced_steer", length=16)
    client_id = steers[0].get("client_id")
    conv_id = executing.get("conv_id")
    user_id = executing.get("user_id")
    generation = executing.get("conversation_generation")
    executing_input_id = executing.get("input_id")
    if not isinstance(client_id, str) or not client_id.strip():
        raise StateError("Forced steer input client identity is unavailable.")
    if not isinstance(conv_id, str) or not isinstance(user_id, int):
        raise StateError("Forced steer conversation identity is invalid.")
    if not isinstance(generation, int) or not isinstance(executing_input_id, str):
        raise StateError("Forced steer execution identity is invalid.")
    source_metadata: JSONDict = {
        "dispatch_mode": FORCED_DISPATCH_MODE,
        "source_input_ids": source_input_ids,
    }
    content_fingerprint = build_conversation_input_content_fingerprint(
        input_type="steer",
        text=text,
        attachment_content=attachments,
        model_settings=None,
        source_metadata=source_metadata,
        media_descriptors=media_descriptors,
    )
    accepted_at_ms = epoch_ms()
    target_input_id = _resolve_settings_source_input_id(conn, executing_input_id)
    conn.execute(
        """
        INSERT INTO webui_conversation_inputs (
            input_id, conv_id, user_id, input_type, transport_origin, text,
            attachment_content_json, model_settings_json, source_key, content_fingerprint,
            client_id, client_request_id, messaging_ingress_id, source_metadata_json,
            media_descriptors_json, state, conversation_generation, target_input_id,
            accepted_at_ms, updated_at_ms
        ) VALUES (?, ?, ?, 'steer', 'chat', ?, ?, NULL, ?, ?, ?, ?, NULL, ?, ?,
                  'pending', ?, ?, ?, ?)
        """,
        (
            input_id,
            conv_id,
            user_id,
            text,
            serialize_json_compact_stable(attachments),
            f"{conv_id}:{client_id.strip()}:{client_request_id}",
            content_fingerprint,
            client_id.strip(),
            client_request_id,
            serialize_json_compact_stable(source_metadata),
            serialize_json_compact_stable(media_descriptors),
            generation,
            target_input_id,
            accepted_at_ms,
            accepted_at_ms,
        ),
    )
    inserted = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT * FROM webui_conversation_inputs WHERE input_id = ? LIMIT 1",
            (input_id,),
        ),
    )
    formatted = format_conversation_input_row(inserted)
    if formatted is None:
        raise StateError("Forced steer input is unavailable after insertion.")
    return (formatted, source_input_ids)


def _settle_source_steers(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    source_input_ids: list[str],
    target_input_id: str,
) -> None:
    terminal_at_ms = epoch_ms()
    terminal_args_json = serialize_json_compact_stable(
        {"forced_input_id": target_input_id},
    )
    for source_input_id in source_input_ids:
        sync_rebind_pending_attachment_references(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            source_input_id=source_input_id,
            target_input_id=target_input_id,
            updated_at_ms=terminal_at_ms,
        )
        cursor = conn.execute(
            """
            UPDATE webui_conversation_inputs
            SET state = 'completed', terminal_code = ?, terminal_args_json = ?,
                terminal_at_ms = ?, updated_at_ms = ?
            WHERE conv_id = ? AND user_id = ? AND input_id = ? AND state = 'pending'
            """,
            (
                FORCED_TERMINAL_CODE,
                terminal_args_json,
                terminal_at_ms,
                terminal_at_ms,
                conv_id,
                user_id,
                source_input_id,
            ),
        )
        if cursor.rowcount != 1:
            raise StateError("Pending steer changed during forced batching.")
        sync_ensure_conversation_input_terminal_event(
            conn,
            input_id=source_input_id,
            user_id=user_id,
            conv_id=conv_id,
            source_message_id=None,
            terminal_state="completed",
            terminal_code=FORCED_TERMINAL_CODE,
            created_at_ms=terminal_at_ms,
        )


def sync_force_pending_conversation_steers(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    request_id: str | None,
    agent_turn_id: str | None,
) -> JSONDict:
    executing_row = _read_executing_input(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        request_id=request_id,
        agent_turn_id=agent_turn_id,
    )
    executing = format_conversation_input_row(executing_row)
    if executing is None:
        return _no_forced_input_result()
    conversation_generation = executing.get("conversation_generation")
    if not isinstance(conversation_generation, int):
        raise StateError("Forced steer conversation generation is invalid.")
    steers = _read_pending_steers(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        conversation_generation=conversation_generation,
    )
    if not steers:
        return _no_forced_input_result()
    first_source_metadata = steers[0].get("source_metadata")
    if (
        len(steers) == 1
        and isinstance(first_source_metadata, dict)
        and first_source_metadata.get("dispatch_mode") == FORCED_DISPATCH_MODE
    ):
        return {
            "forced": True,
            "created": False,
            "input": steers[0],
            "source_input_ids": [],
        }
    forced_input, source_input_ids = _insert_forced_input(
        conn,
        executing=executing,
        steers=steers,
    )
    forced_input_id = str(forced_input["input_id"])
    _settle_source_steers(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        source_input_ids=source_input_ids,
        target_input_id=forced_input_id,
    )
    return {
        "forced": True,
        "created": True,
        "input": forced_input,
        "source_input_ids": source_input_ids,
    }
