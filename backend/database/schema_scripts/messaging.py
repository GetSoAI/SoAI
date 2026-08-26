"""SoAI - Messaging account, sender, and live binding schema [backend/database/schema_scripts/messaging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_messaging_account_schema",)


def apply_messaging_account_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS messaging_accounts (
            account_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            platform TEXT NOT NULL CHECK(platform IN ('telegram', 'whatsapp', 'discord')),
            label TEXT NOT NULL CHECK(length(trim(label)) BETWEEN 1 AND 120),
            principal_id TEXT NOT NULL CHECK(length(trim(principal_id)) BETWEEN 1 AND 255),
            principal_label TEXT CHECK(principal_label IS NULL OR length(trim(principal_label)) BETWEEN 1 AND 255),
            parent_principal_id TEXT CHECK(parent_principal_id IS NULL OR length(trim(parent_principal_id)) BETWEEN 1 AND 255),
            application_principal_id TEXT CHECK(application_principal_id IS NULL OR length(trim(application_principal_id)) BETWEEN 1 AND 255),
            credential_ciphertext TEXT NOT NULL CHECK(length(trim(credential_ciphertext)) > 0),
            credential_fingerprint TEXT NOT NULL CHECK(length(credential_fingerprint) = 64),
            model_settings_json TEXT NOT NULL
                CHECK(json_valid(model_settings_json) AND json_type(model_settings_json) = 'object'),
            locale TEXT NOT NULL CHECK(locale IN ('en', 'it')),
            lifecycle_state TEXT NOT NULL
                CHECK(lifecycle_state IN ('enabled', 'disabled', 'deleting', 'degraded')),
            revision INTEGER NOT NULL CHECK(revision > 0),
            lifecycle_generation INTEGER NOT NULL DEFAULT 0 CHECK(lifecycle_generation >= 0),
            plaintext_secret_replies_enabled INTEGER NOT NULL DEFAULT 0
                CHECK(plaintext_secret_replies_enabled IN (0, 1)),
            accept_messages_from_anyone INTEGER NOT NULL DEFAULT 0
                CHECK(accept_messages_from_anyone IN (0, 1)),
            installed_callback_fingerprint TEXT
                CHECK(installed_callback_fingerprint IS NULL OR length(installed_callback_fingerprint) = 64),
            callback_ownership_state TEXT NOT NULL DEFAULT 'unknown'
                CHECK(callback_ownership_state IN ('unknown', 'owned', 'external', 'lost', 'not_applicable')),
            health_code TEXT CHECK(health_code IS NULL OR length(trim(health_code)) BETWEEN 1 AND 120),
            health_checked_at_ms INTEGER
                CHECK(health_checked_at_ms IS NULL OR health_checked_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            UNIQUE(platform, principal_id),
            UNIQUE(account_id, user_id),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_accounts_owner
            ON messaging_accounts(user_id, updated_at_ms DESC, account_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messaging_accounts_whatsapp_parent
            ON messaging_accounts(parent_principal_id)
            WHERE platform = 'whatsapp' AND parent_principal_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS messaging_authorized_senders (
            account_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            sender_id TEXT NOT NULL CHECK(length(trim(sender_id)) BETWEEN 1 AND 255),
            display_label TEXT CHECK(display_label IS NULL OR length(trim(display_label)) BETWEEN 1 AND 255),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY(account_id, sender_id),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_senders_owner
            ON messaging_authorized_senders(user_id, account_id);
        CREATE TABLE IF NOT EXISTS messaging_thread_bindings (
            account_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            remote_thread_type TEXT NOT NULL CHECK(remote_thread_type IN ('private', 'group', 'channel')),
            remote_thread_key TEXT NOT NULL CHECK(length(trim(remote_thread_key)) BETWEEN 1 AND 512),
            conv_id TEXT NOT NULL UNIQUE,
            binding_generation INTEGER NOT NULL DEFAULT 0 CHECK(binding_generation >= 0),
            pending_reset_control_id TEXT,
            pending_reset_state TEXT CHECK(pending_reset_state IS NULL OR pending_reset_state IN ('accepted', 'committed')),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY(account_id, remote_thread_type, remote_thread_key),
            FOREIGN KEY(account_id, user_id) REFERENCES messaging_accounts(account_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messaging_bindings_owner
            ON messaging_thread_bindings(user_id, conv_id);
        """,
    )
