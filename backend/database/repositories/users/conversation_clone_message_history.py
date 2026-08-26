"""SoAI - Conversation clone message and attachment history [backend/database/repositories/users/conversation_clone_message_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_unavailable_content_part,
    validate_soai_knowledge_unavailable_content_part,
)
from core.conversations.message_content_validation import validate_webui_message_content_json
from core.serialization.json import serialize_json_compact_stable_strict
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sqlite_row_scalars import (
    require_sqlite_row_non_empty_str,
    require_sqlite_row_str,
)
from database.repositories.users.conversation_clone_attachments import (
    ConversationCloneAttachmentHistory,
)
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)
from database.repositories.users.message_storage_rows import MESSAGE_INSERT_SQL

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = ("copy_cloned_message_history",)

_MESSAGE_ROW_LABEL = "Cloned message row field"


def _rewrite_content_part(
    *,
    part: JSONDict,
    attachments: ConversationCloneAttachmentHistory,
) -> JSONDict:
    part_type = part.get("type")
    if part_type == "soai_file":
        return attachments.rewrite_file(part)
    if part_type == "soai_knowledge":
        return attachments.rewrite_knowledge(part)
    if part_type == "soai_file_unavailable":
        return validate_soai_file_unavailable_content_part(part)
    if part_type == "soai_knowledge_unavailable":
        return validate_soai_knowledge_unavailable_content_part(part)
    return part


def _rewritten_content_json(
    *,
    row: SQLiteRowDict,
    attachments: ConversationCloneAttachmentHistory,
) -> str:
    content_json = require_sqlite_row_str(row, "content", label=_MESSAGE_ROW_LABEL)
    content = safe_json_deserialize(content_json)
    role = require_sqlite_row_non_empty_str(row, "role", label=_MESSAGE_ROW_LABEL)
    validated_content = validate_webui_message_content_json(content, role=role)
    if isinstance(validated_content, str):
        return content_json
    rewritten: list[JSONDict] = []
    changed = False
    for part in validated_content:
        rewritten_part = _rewrite_content_part(
            part=part,
            attachments=attachments,
        )
        rewritten.append(rewritten_part)
        if rewritten_part != part:
            changed = True
    if not changed:
        return content_json
    return serialize_json_compact_stable_strict(rewritten)


def _message_insert_values(
    row: SQLiteRowDict,
    *,
    target_conv_id: str,
    content_json: str,
) -> tuple[SQLiteValue, ...]:
    content_length, content_sha256 = build_message_content_integrity(content_json)
    finalized_at_ms = None if row["role"] == "assistant" else row["finalized_at_ms"]
    return (
        target_conv_id,
        row["role"],
        row["message_type"],
        content_json,
        content_length,
        content_sha256,
        finalized_at_ms,
        row["created_at_ms"],
        row["assistant_turn_at_ms"],
        row["model_variant_index"],
        row["request_id"],
        row["model_id"],
        row["prompt_tokens"],
        row["completion_tokens"],
        row["total_tokens"],
        row["usage_source"],
        row["generation_latency_ms"],
        row["finish_reason"],
        row["thinking_tail_duration_ms"],
    )


def copy_cloned_message_history(
    conn: sqlite3.Connection,
    *,
    source_conv_id: str,
    target_conv_id: str,
    user_id: int,
) -> None:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            """
            SELECT role, message_type, content, created_at_ms, assistant_turn_at_ms,
                   model_variant_index, finalized_at_ms, request_id, model_id,
                   prompt_tokens, completion_tokens, total_tokens, usage_source,
                   generation_latency_ms, finish_reason, thinking_tail_duration_ms
            FROM webui_messages
            WHERE conv_id = ?
            ORDER BY created_at_ms ASC, id ASC
            """,
            (source_conv_id,),
        ),
    )
    attachments = ConversationCloneAttachmentHistory(
        conn=conn,
        source_conv_id=source_conv_id,
        target_conv_id=target_conv_id,
        user_id=user_id,
    )
    for row in rows:
        content_json = _rewritten_content_json(
            row=row,
            attachments=attachments,
        )
        conn.execute(
            MESSAGE_INSERT_SQL,
            _message_insert_values(
                row,
                target_conv_id=target_conv_id,
                content_json=content_json,
            ),
        )
