"""SoAI - Messaging remote interaction route schema [backend/database/schema_scripts/messaging_interactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_messaging_interaction_schema",)


def apply_messaging_interaction_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS messaging_interaction_routes (
            route_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            account_generation INTEGER NOT NULL CHECK(account_generation >= 0),
            binding_generation INTEGER NOT NULL CHECK(binding_generation >= 0),
            remote_thread_type TEXT NOT NULL CHECK(remote_thread_type IN ('private', 'group', 'channel')),
            remote_thread_key TEXT NOT NULL CHECK(length(trim(remote_thread_key)) BETWEEN 1 AND 512),
            conv_id TEXT NOT NULL,
            input_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            interaction_type TEXT NOT NULL CHECK(interaction_type IN ('tool_approval', 'ask_user', 'vault_secret_request')),
            originating_sender_id TEXT NOT NULL CHECK(length(trim(originating_sender_id)) BETWEEN 1 AND 255),
            tool_call_id TEXT,
            argument_hash TEXT CHECK(argument_hash IS NULL OR length(argument_hash) = 64),
            reply_token_hash TEXT NOT NULL CHECK(length(reply_token_hash) = 64),
            focus_nonce_hash TEXT NOT NULL CHECK(length(focus_nonce_hash) = 64),
            provider_prompt_message_id TEXT,
            checkpoint_generation INTEGER NOT NULL CHECK(checkpoint_generation > 0),
            state TEXT NOT NULL CHECK(state IN (
                'pending', 'resolving', 'expiring', 'resolved', 'expired', 'cancelled'
            )),
            resolution_ingress_id TEXT UNIQUE,
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            resolved_at_ms INTEGER CHECK(resolved_at_ms IS NULL OR resolved_at_ms >= {EPOCH_MS_MIN}),
            UNIQUE(account_id, task_id),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_interactions_lookup
            ON messaging_interaction_routes(account_id, remote_thread_type, remote_thread_key,
                originating_sender_id, state, expires_at_ms);
        """,
    )
