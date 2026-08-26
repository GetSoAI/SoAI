"""SoAI - Database schema: conversation attachments [backend/database/schema_scripts/conversation_attachments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_conversation_attachments_schema",)


def _build_conversation_attachments_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_conversation_attachments (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            file_id TEXT NOT NULL,
            client_attachment_id TEXT NOT NULL CHECK(length(trim(client_attachment_id)) > 0),
            filename TEXT NOT NULL CHECK(length(trim(filename)) > 0),
            mime_type TEXT NOT NULL CHECK(length(trim(mime_type)) > 0),
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            preview_type TEXT NOT NULL CHECK(preview_type IN ('text', 'image', 'audio', 'video', 'document', 'file')),
            provider_mode TEXT CHECK(provider_mode IS NULL OR provider_mode IN ('image', 'text', 'reference')),
            provider_text TEXT,
            provider_text_truncated INTEGER CHECK(provider_text_truncated IS NULL OR provider_text_truncated IN (0, 1)),
            parse_state TEXT NOT NULL CHECK(parse_state IN ('pending', 'ready', 'failed')),
            parse_error TEXT,
            parsed_at_ms INTEGER CHECK(parsed_at_ms IS NULL OR parsed_at_ms >= {EPOCH_MS_MIN}),
            state TEXT NOT NULL CHECK(state IN ('staged', 'queued', 'committed', 'unused')),
            conversation_input_id TEXT,
            message_created_at_ms INTEGER CHECK(message_created_at_ms IS NULL OR message_created_at_ms >= {EPOCH_MS_MIN}),
            attachment_revision INTEGER NOT NULL CHECK(attachment_revision >= 0),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(file_id) REFERENCES files_catalog(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE SET NULL
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_conversation_attachments_client
            ON webui_conversation_attachments(conv_id, user_id, client_attachment_id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_attachments_file_owner
            ON webui_conversation_attachments(file_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_attachments_cleanup
            ON webui_conversation_attachments(state, expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_attachments_pending_parse
            ON webui_conversation_attachments(parse_state, expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_attachments_conversation_input
            ON webui_conversation_attachments(conversation_input_id, conv_id, user_id);

        CREATE TABLE IF NOT EXISTS webui_conversation_knowledge_attachments (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            state TEXT NOT NULL CHECK(state IN ('draft', 'queued', 'committed', 'unused')),
            conversation_input_id TEXT,
            message_created_at_ms INTEGER CHECK(message_created_at_ms IS NULL OR message_created_at_ms >= {EPOCH_MS_MIN}),
            processing_state TEXT NOT NULL CHECK(processing_state IN ('pending', 'running', 'cancelling', 'ready', 'error', 'cancelled')),
            source_type TEXT NOT NULL CHECK(source_type IN ('composer_document_upload', 'composer_folder_upload', 'knowledge_tab_document_upload', 'knowledge_tab_folder_upload', 'file_explorer_folder_import', 'document_delete', 'bulk_delete', 'reindex', 'linked_knowledge')),
            operation_type TEXT NOT NULL CHECK(operation_type IN ('added', 'removed', 'updated', 'reindexed')),
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            root_label TEXT,
            root_virtual_path TEXT,
            task_id TEXT,
            client_batch_id TEXT,
            first_event_id INTEGER,
            last_event_id INTEGER,
            state_signature TEXT,
            total_count INTEGER NOT NULL CHECK(total_count >= 0),
            visible_count INTEGER NOT NULL CHECK(visible_count >= 0),
            hidden_count INTEGER NOT NULL CHECK(hidden_count >= 0),
            status_counts_json TEXT NOT NULL CHECK(json_valid(status_counts_json) AND json_type(status_counts_json)='object'),
            attachment_revision INTEGER NOT NULL CHECK(attachment_revision >= 0),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            finalized_at_ms INTEGER CHECK(finalized_at_ms IS NULL OR finalized_at_ms >= {EPOCH_MS_MIN}),
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE SET NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_draft
            ON webui_conversation_knowledge_attachments(conv_id, user_id, state);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_cleanup
            ON webui_conversation_knowledge_attachments(state, expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_task
            ON webui_conversation_knowledge_attachments(task_id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_conversation_input
            ON webui_conversation_knowledge_attachments(conversation_input_id, conv_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_reusable
            ON webui_conversation_knowledge_attachments(user_id, state, updated_at_ms);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_identity
            ON webui_conversation_knowledge_attachments(id, conv_id, user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_attachments_client_batch
            ON webui_conversation_knowledge_attachments(conv_id, user_id, client_batch_id)
            WHERE client_batch_id IS NOT NULL AND state IN ('draft', 'queued', 'committed');

        CREATE TABLE IF NOT EXISTS webui_conversation_knowledge_attachment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_attachment_id TEXT NOT NULL,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            document_id TEXT,
            event_id INTEGER,
            item_index INTEGER NOT NULL CHECK(item_index >= 0),
            filename TEXT NOT NULL CHECK(length(trim(filename)) > 0),
            file_type TEXT,
            file_size_bytes INTEGER CHECK(file_size_bytes IS NULL OR file_size_bytes >= 0),
            rag_status TEXT CHECK(rag_status IS NULL OR rag_status IN ('queued', 'fetching', 'parsing', 'chunking', 'embedding', 'completed', 'error', 'cancelled', 'skipped')),
            operation_type TEXT NOT NULL CHECK(operation_type IN ('added', 'removed', 'updated', 'reindexed')),
            error_message TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(knowledge_attachment_id) REFERENCES webui_conversation_knowledge_attachments(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_page
            ON webui_conversation_knowledge_attachment_items(knowledge_attachment_id, item_index, id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_owner
            ON webui_conversation_knowledge_attachment_items(conv_id, user_id, knowledge_attachment_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_identity
            ON webui_conversation_knowledge_attachment_items(id, knowledge_attachment_id);
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_document
            ON webui_conversation_knowledge_attachment_items(document_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_document_unique
            ON webui_conversation_knowledge_attachment_items(knowledge_attachment_id, document_id)
            WHERE document_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_knowledge_items_event
            ON webui_conversation_knowledge_attachment_items(event_id);
        """


def apply_conversation_attachments_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_conversation_attachments_schema_sql())
