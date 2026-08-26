"""SoAI - Transactional conversation clone attachment ownership [backend/database/repositories/users/conversation_clone_attachments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field

from core.attachments.attachment_content_parts import (
    content_part_from_file_attachment,
    content_part_from_unavailable_file,
    content_part_from_unavailable_knowledge,
)
from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
    validate_soai_knowledge_content_part,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)

__all__ = ("ConversationCloneAttachmentHistory",)


@dataclass(slots=True)
class ConversationCloneAttachmentHistory:
    conn: sqlite3.Connection
    source_conv_id: str
    target_conv_id: str
    user_id: int
    file_parts_by_source_snapshot: dict[str, JSONDict | None] = field(
        default_factory=dict[str, JSONDict | None]
    )

    def _clone_file(self, part: JSONDict) -> JSONDict | None:
        source_attachment_id = str(part["attachment_id"])
        source = fetch_file_attachment_by_id(
            self.conn,
            conv_id=self.source_conv_id,
            user_id=self.user_id,
            attachment_id=source_attachment_id,
        )
        if source is None or source["state"] != "committed" or source["parse_state"] != "ready":
            return None
        if content_part_from_file_attachment(source) != part:
            return None
        target_attachment_id = f"att_{uuid.uuid4().hex}"
        inserted = self.conn.execute(
            """
            INSERT INTO webui_conversation_attachments (
                id, conv_id, user_id, file_id, client_attachment_id, filename,
                mime_type, size_bytes, preview_type, provider_mode, provider_text,
                provider_text_truncated, parse_state, parse_error, parsed_at_ms,
                state, conversation_input_id, message_created_at_ms,
                attachment_revision, created_at_ms, updated_at_ms, expires_at_ms
            )
            SELECT ?, ?, user_id, file_id, client_attachment_id, filename,
                   mime_type, size_bytes, preview_type, provider_mode, provider_text,
                   provider_text_truncated, parse_state, parse_error, parsed_at_ms,
                   state, NULL, message_created_at_ms, attachment_revision,
                   created_at_ms, updated_at_ms, expires_at_ms
            FROM webui_conversation_attachments
            WHERE id = ? AND conv_id = ? AND user_id = ?
              AND state = 'committed' AND parse_state = 'ready'
            """,
            (
                target_attachment_id,
                self.target_conv_id,
                source_attachment_id,
                self.source_conv_id,
                self.user_id,
            ),
        ).rowcount
        if inserted != 1:
            return None
        cloned = dict(part)
        cloned["attachment_id"] = target_attachment_id
        return cloned

    def rewrite_file(self, part: JSONDict) -> JSONDict:
        validated = validate_soai_file_content_part(part)
        source_snapshot = serialize_json_compact_stable_strict(validated)
        if source_snapshot not in self.file_parts_by_source_snapshot:
            self.file_parts_by_source_snapshot[source_snapshot] = self._clone_file(validated)
        cloned = self.file_parts_by_source_snapshot[source_snapshot]
        return cloned if cloned is not None else content_part_from_unavailable_file(validated)

    def rewrite_knowledge(self, part: JSONDict) -> JSONDict:
        validated = validate_soai_knowledge_content_part(part)
        return content_part_from_unavailable_knowledge(validated)
