"""SoAI - Messaging delivery and interaction routing schema [backend/database/schema_scripts/messaging_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_messaging_delivery_schema",)


def apply_messaging_delivery_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS messaging_deliveries (
            delivery_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            remote_thread_type TEXT NOT NULL CHECK(remote_thread_type IN ('private', 'group', 'channel')),
            remote_thread_key TEXT NOT NULL CHECK(length(trim(remote_thread_key)) BETWEEN 1 AND 512),
            originating_sender_id TEXT NOT NULL CHECK(length(trim(originating_sender_id)) BETWEEN 1 AND 255),
            account_generation INTEGER NOT NULL CHECK(account_generation >= 0),
            binding_generation INTEGER NOT NULL CHECK(binding_generation >= 0),
            source_event_id TEXT NOT NULL UNIQUE CHECK(length(trim(source_event_id)) > 0),
            source_input_id TEXT,
            source_message_id INTEGER,
            purpose TEXT NOT NULL CHECK(purpose IN ('assistant', 'interaction', 'control')),
            state TEXT NOT NULL CHECK(state IN ('pending', 'sending', 'sent', 'failed', 'skipped', 'delivery_unknown')),
            provider_message_id TEXT,
            receipt_state TEXT
                CHECK(receipt_state IS NULL OR receipt_state IN ('sent', 'delivered', 'read', 'failed')),
            receipt_at_ms INTEGER
                CHECK(receipt_at_ms IS NULL OR receipt_at_ms >= {EPOCH_MS_MIN}),
            failure_code TEXT CHECK(failure_code IS NULL OR length(trim(failure_code)) BETWEEN 1 AND 120),
            claim_generation INTEGER NOT NULL DEFAULT 0 CHECK(claim_generation >= 0),
            claim_owner TEXT,
            claim_server_boot_id TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            next_attempt_at_ms INTEGER NOT NULL DEFAULT 0 CHECK(next_attempt_at_ms >= 0),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            started_at_ms INTEGER CHECK(started_at_ms IS NULL OR started_at_ms >= {EPOCH_MS_MIN}),
            terminal_at_ms INTEGER CHECK(terminal_at_ms IS NULL OR terminal_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            CHECK((purpose = 'assistant' AND source_input_id IS NOT NULL)
                OR purpose != 'assistant'),
            CHECK(state != 'sending' OR (
                claim_generation > 0 AND claim_owner IS NOT NULL AND claim_server_boot_id IS NOT NULL
                AND started_at_ms IS NOT NULL
            )),
            CHECK(state NOT IN ('sent', 'failed', 'skipped', 'delivery_unknown') OR terminal_at_ms IS NOT NULL),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY(source_input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE CASCADE,
            FOREIGN KEY(source_message_id) REFERENCES webui_messages(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_delivery_due
            ON messaging_deliveries(state, next_attempt_at_ms, created_at_ms, delivery_id);
        CREATE INDEX IF NOT EXISTS idx_messaging_delivery_thread_fifo
            ON messaging_deliveries(
                account_id, remote_thread_type, remote_thread_key, state,
                created_at_ms, delivery_id
            );
        CREATE TABLE IF NOT EXISTS messaging_delivery_chunks (
            delivery_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
            content_text TEXT NOT NULL CHECK(length(content_text) > 0),
            content_hash TEXT NOT NULL CHECK(length(content_hash) = 64),
            provider_message_id TEXT,
            receipt_state TEXT
                CHECK(receipt_state IS NULL OR receipt_state IN ('sent', 'delivered', 'read', 'failed')),
            receipt_at_ms INTEGER
                CHECK(receipt_at_ms IS NULL OR receipt_at_ms >= {EPOCH_MS_MIN}),
            state TEXT NOT NULL CHECK(state IN ('pending', 'sending', 'sent', 'failed', 'delivery_unknown')),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            request_started_at_ms INTEGER
                CHECK(request_started_at_ms IS NULL OR request_started_at_ms >= {EPOCH_MS_MIN}),
            terminal_at_ms INTEGER
                CHECK(terminal_at_ms IS NULL OR terminal_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            CHECK(state NOT IN ('sent', 'failed', 'delivery_unknown') OR terminal_at_ms IS NOT NULL),
            PRIMARY KEY(delivery_id, ordinal),
            FOREIGN KEY(delivery_id) REFERENCES messaging_deliveries(delivery_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_chunks_state
            ON messaging_delivery_chunks(delivery_id, state, ordinal);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messaging_chunks_one_sending
            ON messaging_delivery_chunks(delivery_id)
            WHERE state = 'sending';
        """,
    )
