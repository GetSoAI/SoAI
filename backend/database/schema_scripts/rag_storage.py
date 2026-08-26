"""SoAI - Database schema: RAG storage tables [backend/database/schema_scripts/rag_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_rag_storage_schema",)


def _build_rag_storage_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            file_id TEXT,
            filename TEXT NOT NULL CHECK(length(trim(filename)) > 0),
            file_type TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL CHECK(file_size_bytes >= 0),
            status TEXT NOT NULL CHECK(status IN ('queued', 'fetching', 'parsing', 'chunking', 'embedding', 'completed', 'error', 'cancelled')),
            status_details TEXT,
            source_type TEXT NOT NULL CHECK(source_type IN ('upload', 'url', 'chat', 'mcp')),
            source_url TEXT,
            chunking_strategy TEXT NOT NULL DEFAULT 'token_based' CHECK(chunking_strategy IN ('token_based', 'fixed_size', 'paragraph', 'semantic')),
            chunk_size INTEGER NOT NULL DEFAULT 500 CHECK(chunk_size > 0),
            chunk_overlap INTEGER NOT NULL DEFAULT 100 CHECK(chunk_overlap >= 0),
            content_hash TEXT,
            total_chunks INTEGER,
            processed_chunks INTEGER,
            embedding_model TEXT,
            effective_embedding_model TEXT,
            embedding_dimensions INTEGER,
            metadata TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            processing_started_at_ms INTEGER,
            processing_completed_at_ms INTEGER,
            error_message TEXT,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(file_id) REFERENCES files_catalog(id) ON DELETE SET NULL
        ) STRICT;
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            token_count INTEGER,
            start_char INTEGER,
            end_char INTEGER,
            metadata TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(document_id) REFERENCES rag_documents(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_rag_documents_conversation ON rag_documents(conv_id, created_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_user ON rag_documents(user_id);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_file ON rag_documents(file_id);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_cache_lookup ON rag_documents(conv_id, status, content_hash, chunking_strategy, chunk_size, chunk_overlap, embedding_model);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_source_url_cache ON rag_documents(conv_id, status, source_url, created_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_processing_task ON rag_documents(conv_id, json_extract(metadata, '$.task_id')) WHERE status IN ('queued', 'fetching', 'parsing', 'chunking', 'embedding');
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id, chunk_index);
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_hash ON rag_chunks(content_hash);
        CREATE TABLE IF NOT EXISTS rag_conversation_config (
            conv_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)),
            retrieval_strategy TEXT NOT NULL DEFAULT 'similarity' CHECK(retrieval_strategy IN ('similarity', 'mmr', 'hybrid')),
            top_k INTEGER NOT NULL DEFAULT 5 CHECK(top_k > 0),
            similarity_threshold REAL NOT NULL DEFAULT 0.3 CHECK(similarity_threshold >= 0.0 AND similarity_threshold <= 1.0),
            chunking_strategy TEXT NOT NULL DEFAULT 'token_based' CHECK(chunking_strategy IN ('token_based', 'fixed_size', 'paragraph', 'semantic')),
            chunk_size INTEGER NOT NULL DEFAULT 500 CHECK(chunk_size > 0),
            chunk_overlap INTEGER NOT NULL DEFAULT 100 CHECK(chunk_overlap >= 0),
            embedding_model TEXT,
            config_metadata TEXT CHECK(config_metadata IS NULL OR json_valid(config_metadata)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_modified_at_ms INTEGER NOT NULL CHECK(last_modified_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) STRICT;
        CREATE TABLE IF NOT EXISTS rag_vector_collections (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            collection_name TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimensions INTEGER NOT NULL,
            document_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            metadata TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_synced_at_ms INTEGER NOT NULL CHECK(last_synced_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES rag_conversation_config(conv_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_rag_vectors_conversation ON rag_vector_collections(conv_id);
        CREATE TABLE IF NOT EXISTS rag_knowledge_prompt_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN (
                'documents_added',
                'documents_removed',
                'document_processing_completed',
                'document_processing_failed',
                'document_processing_cancelled',
                'knowledge_reindex_queued',
                'knowledge_reindex_completed',
                'knowledge_reindex_failed',
                'knowledge_reindex_cancelled'
            )),
            document_names_json TEXT NOT NULL CHECK(json_valid(document_names_json)),
            document_count INTEGER NOT NULL,
            details_json TEXT NOT NULL CHECK(json_valid(details_json)),
            created_at_ms INTEGER NOT NULL,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_rag_knowledge_prompt_events_delivery
            ON rag_knowledge_prompt_events(conv_id, user_id, id DESC);
        CREATE TABLE IF NOT EXISTS rag_processing_jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL CHECK(job_type IN ('document_upload', 'web_fetch_ingest', 'reindex')),
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            document_id TEXT,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'retryable', 'completed', 'failed', 'cancelled')),
            payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
            spool_path TEXT,
            lease_token TEXT,
            lease_owner TEXT,
            lease_expires_at_ms INTEGER CHECK(lease_expires_at_ms IS NULL OR lease_expires_at_ms >= {EPOCH_MS_MIN}),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            last_error TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            completed_at_ms INTEGER CHECK(completed_at_ms IS NULL OR completed_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES rag_documents(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_rag_processing_jobs_claimable
            ON rag_processing_jobs(status, lease_expires_at_ms, updated_at_ms);
        CREATE INDEX IF NOT EXISTS idx_rag_processing_jobs_conversation
            ON rag_processing_jobs(conv_id, status, updated_at_ms);
        CREATE INDEX IF NOT EXISTS idx_rag_processing_jobs_document
            ON rag_processing_jobs(document_id, status);
        CREATE TABLE IF NOT EXISTS rag_conversation_maintenance_locks (
            conv_id TEXT PRIMARY KEY,
            lock_type TEXT NOT NULL CHECK(lock_type IN ('reindex', 'delete_all')),
            owner_task_id TEXT NOT NULL,
            lease_token TEXT NOT NULL,
            lease_owner TEXT NOT NULL,
            lease_expires_at_ms INTEGER NOT NULL CHECK(lease_expires_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_rag_maintenance_locks_expires
            ON rag_conversation_maintenance_locks(lease_expires_at_ms);
        CREATE TABLE IF NOT EXISTS rag_linked_documents (
            id TEXT PRIMARY KEY,
            target_conv_id TEXT NOT NULL,
            target_user_id INTEGER NOT NULL CHECK(target_user_id > 0),
            target_knowledge_attachment_id TEXT NOT NULL,
            target_item_id INTEGER NOT NULL CHECK(target_item_id > 0),
            source_conv_id TEXT NOT NULL,
            source_user_id INTEGER NOT NULL CHECK(source_user_id > 0),
            source_document_id TEXT NOT NULL,
            source_knowledge_attachment_id TEXT NOT NULL,
            source_item_id INTEGER NOT NULL CHECK(source_item_id > 0),
            status TEXT NOT NULL CHECK(status IN ('active', 'unavailable')),
            unavailable_reason TEXT,
            client_batch_id TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            CHECK(
                (status = 'active' AND unavailable_reason IS NULL)
                OR (status = 'unavailable' AND length(trim(unavailable_reason)) > 0)
            ),
            FOREIGN KEY(target_conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(target_user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(target_knowledge_attachment_id, target_conv_id, target_user_id)
                REFERENCES webui_conversation_knowledge_attachments(id, conv_id, user_id)
                ON DELETE CASCADE,
            FOREIGN KEY(target_item_id, target_knowledge_attachment_id)
                REFERENCES webui_conversation_knowledge_attachment_items(id, knowledge_attachment_id)
                ON DELETE CASCADE
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_linked_documents_target_document
            ON rag_linked_documents(target_knowledge_attachment_id, source_document_id);
        CREATE INDEX IF NOT EXISTS idx_rag_linked_documents_target_lookup
            ON rag_linked_documents(target_conv_id, target_user_id, status);
        CREATE INDEX IF NOT EXISTS idx_rag_linked_documents_attachment_lookup
            ON rag_linked_documents(target_knowledge_attachment_id, status);
        CREATE INDEX IF NOT EXISTS idx_rag_linked_documents_source_lookup
            ON rag_linked_documents(source_conv_id, source_document_id);
        CREATE INDEX IF NOT EXISTS idx_rag_linked_documents_source_document
            ON rag_linked_documents(source_document_id);
        CREATE TABLE IF NOT EXISTS rag_knowledge_prompt_delivery (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            last_delivered_event_id INTEGER NOT NULL DEFAULT 0,
            last_delivered_state_signature TEXT,
            active_claim_id TEXT,
            active_claim_request_id TEXT,
            active_claim_event_ceiling_id INTEGER,
            active_claim_state_signature TEXT,
            active_claim_expires_at_ms INTEGER,
            last_delivered_at_ms INTEGER,
            PRIMARY KEY (conv_id, user_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        """


def apply_rag_storage_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_rag_storage_schema_sql())
