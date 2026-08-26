"""SoAI - Conversation attachment draft reference SQL [backend/database/repositories/users/conversation_attachment_draft_reference_sql.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("attachment_not_referenced_by_draft_sql",)


def attachment_not_referenced_by_draft_sql(attachment_alias: str) -> str:
    return f"""
          AND NOT EXISTS (
              SELECT 1
              FROM webui_conversation_drafts d, json_each(d.attachment_content_json) entry
              WHERE d.conv_id = {attachment_alias}.conv_id
                AND d.user_id = {attachment_alias}.user_id
                AND d.is_deleted = 0
                AND json_extract(entry.value, '$.type') = 'soai_file'
                AND json_extract(entry.value, '$.attachment_id') = {attachment_alias}.id
          )
        """
