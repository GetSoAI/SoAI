"""SoAI - Messaging ingress and Discord checkpoint schema [backend/database/schema_scripts/messaging_ingress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_messaging_ingress_schema",)


def apply_messaging_ingress_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS messaging_ingress_events (
            ingress_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            platform TEXT NOT NULL CHECK(platform IN ('telegram', 'whatsapp', 'discord')),
            remote_thread_type TEXT NOT NULL CHECK(remote_thread_type IN ('private', 'group', 'channel')),
            remote_thread_key TEXT NOT NULL CHECK(length(trim(remote_thread_key)) BETWEEN 1 AND 512),
            provider_event_id TEXT NOT NULL CHECK(length(trim(provider_event_id)) BETWEEN 1 AND 512),
            provider_message_id TEXT
                CHECK(provider_message_id IS NULL OR length(trim(provider_message_id)) BETWEEN 1 AND 512),
            discord_dispatch_sequence INTEGER CHECK(discord_dispatch_sequence IS NULL OR discord_dispatch_sequence >= 0),
            provider_timestamp_ms INTEGER
                CHECK(provider_timestamp_ms IS NULL OR provider_timestamp_ms >= {EPOCH_MS_MIN}),
            content_fingerprint TEXT NOT NULL CHECK(length(content_fingerprint) = 64),
            sender_id TEXT CHECK(sender_id IS NULL OR length(trim(sender_id)) BETWEEN 1 AND 255),
            provider_receipt_state TEXT
                CHECK(provider_receipt_state IS NULL OR provider_receipt_state IN ('sent', 'delivered', 'read', 'failed')),
            account_generation INTEGER CHECK(account_generation IS NULL OR account_generation >= 0),
            binding_generation INTEGER CHECK(binding_generation IS NULL OR binding_generation >= 0),
            classification TEXT NOT NULL CHECK(classification IN ('prompt', 'control', 'interaction', 'protocol', 'unsupported', 'unauthorized')),
            outcome TEXT NOT NULL CHECK(outcome IN ('accepted', 'duplicate', 'ignored', 'rejected', 'failed')),
            linked_input_id TEXT,
            linked_control_id TEXT,
            linked_interaction_route_id TEXT,
            interaction_resolution_json TEXT
                CHECK(interaction_resolution_json IS NULL OR (
                    json_valid(interaction_resolution_json)
                    AND json_type(interaction_resolution_json) = 'object'
                )),
            old_conv_id TEXT,
            result_conv_id TEXT,
            diagnostic_code TEXT CHECK(diagnostic_code IS NULL OR length(trim(diagnostic_code)) BETWEEN 1 AND 120),
            received_at_ms INTEGER NOT NULL CHECK(received_at_ms >= {EPOCH_MS_MIN}),
            processed_at_ms INTEGER NOT NULL CHECK(processed_at_ms >= {EPOCH_MS_MIN}),
            UNIQUE(account_id, provider_event_id),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY(linked_input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE SET NULL,
            FOREIGN KEY(old_conv_id) REFERENCES webui_conversations(id) ON DELETE SET NULL,
            FOREIGN KEY(result_conv_id) REFERENCES webui_conversations(id) ON DELETE SET NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_ingress_thread
            ON messaging_ingress_events(account_id, remote_thread_type, remote_thread_key, received_at_ms);
        CREATE TABLE IF NOT EXISTS messaging_discord_sessions (
            account_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            connection_generation INTEGER NOT NULL CHECK(connection_generation >= 0),
            session_id TEXT CHECK(session_id IS NULL OR length(trim(session_id)) BETWEEN 1 AND 255),
            resume_gateway_url TEXT CHECK(resume_gateway_url IS NULL OR length(trim(resume_gateway_url)) BETWEEN 1 AND 2048),
            committed_dispatch_sequence INTEGER CHECK(committed_dispatch_sequence IS NULL OR committed_dispatch_sequence >= 0),
            session_state TEXT NOT NULL CHECK(session_state IN ('new', 'resumable', 'gap', 'closed')),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE
        ) STRICT;
        """,
    )
