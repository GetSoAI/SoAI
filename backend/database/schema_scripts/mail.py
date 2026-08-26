"""SoAI - Database schema for mail accounts and cache [backend/database/schema_scripts/mail.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.account_identifiers import (
    MAIL_ACCOUNT_ID_PREFIX,
    MAIL_ATTACHMENT_ID_PREFIX,
    MAIL_FOLDER_ID_PREFIX,
    MAIL_MESSAGE_ID_PREFIX,
)
from database.sql.script import execute_sql_script

__all__ = ("apply_mail_schema",)


def apply_mail_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS mail_accounts (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{MAIL_ACCOUNT_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            external_account_id TEXT NOT NULL UNIQUE,
            protocol TEXT NOT NULL CHECK(protocol IN ('imap', 'pop3')),
            inbound_host TEXT NOT NULL,
            inbound_port INTEGER NOT NULL CHECK(inbound_port >= 1),
            inbound_security TEXT NOT NULL CHECK(inbound_security IN ('tls', 'starttls')),
            smtp_host TEXT NOT NULL,
            smtp_port INTEGER NOT NULL CHECK(smtp_port >= 1),
            smtp_security TEXT NOT NULL CHECK(smtp_security IN ('tls', 'starttls')),
            folder_mapping_json TEXT,
            last_sync_at_ms INTEGER,
            last_sync_error TEXT,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(external_account_id) REFERENCES external_accounts(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_mail_accounts_user_created
            ON mail_accounts(user_id, created_at_ms DESC, id DESC);
        CREATE TABLE IF NOT EXISTS mail_folders (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{MAIL_FOLDER_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            mail_account_id TEXT NOT NULL,
            remote_mailbox TEXT NOT NULL,
            name TEXT NOT NULL,
            special_use TEXT,
            subscribed INTEGER NOT NULL CHECK(subscribed IN (0, 1)),
            unread_count INTEGER NOT NULL CHECK(unread_count >= 0) DEFAULT 0,
            message_count INTEGER NOT NULL CHECK(message_count >= 0) DEFAULT 0,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
            UNIQUE(mail_account_id, remote_mailbox)
        );
        CREATE INDEX IF NOT EXISTS idx_mail_folders_account_name
            ON mail_folders(mail_account_id, name COLLATE NOCASE, id DESC);
        CREATE TABLE IF NOT EXISTS mail_messages (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{MAIL_MESSAGE_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            mail_account_id TEXT NOT NULL,
            folder_id TEXT NOT NULL,
            remote_mailbox TEXT,
            uidvalidity INTEGER,
            uid INTEGER,
            uidl TEXT,
            thread_id TEXT NOT NULL,
            rfc822_message_id TEXT,
            in_reply_to_message_id TEXT,
            references_json TEXT,
            subject TEXT NOT NULL,
            from_json TEXT NOT NULL,
            to_json TEXT NOT NULL,
            cc_json TEXT,
            bcc_json TEXT,
            sent_at_ms INTEGER,
            received_at_ms INTEGER NOT NULL,
            snippet TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            unread INTEGER NOT NULL CHECK(unread IN (0, 1)),
            flagged INTEGER NOT NULL CHECK(flagged IN (0, 1)),
            has_attachments INTEGER NOT NULL CHECK(has_attachments IN (0, 1)),
            attachment_count INTEGER NOT NULL CHECK(attachment_count >= 0),
            deleted_original_folder_id TEXT,
            invite_json TEXT,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY(folder_id) REFERENCES mail_folders(id) ON DELETE CASCADE,
            CHECK(
                (uidl IS NOT NULL AND uid IS NULL AND uidvalidity IS NULL)
                OR
                (
                    uidl IS NULL
                    AND uid IS NOT NULL
                    AND uidvalidity IS NOT NULL
                    AND remote_mailbox IS NOT NULL
                )
            )
        );
        CREATE INDEX IF NOT EXISTS idx_mail_messages_folder_received
            ON mail_messages(folder_id, received_at_ms DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_mail_messages_account_message_id
            ON mail_messages(mail_account_id, rfc822_message_id, id DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_messages_imap_identity
            ON mail_messages(mail_account_id, remote_mailbox, uidvalidity, uid)
            WHERE uid IS NOT NULL AND uidvalidity IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_messages_pop3_identity
            ON mail_messages(mail_account_id, uidl)
            WHERE uidl IS NOT NULL;
        CREATE TABLE IF NOT EXISTS mail_message_bodies (
            message_id TEXT PRIMARY KEY NOT NULL,
            body_text TEXT NOT NULL,
            body_html TEXT,
            total_chars INTEGER NOT NULL CHECK(total_chars >= 0),
            cached_at_ms INTEGER NOT NULL,
            FOREIGN KEY(message_id) REFERENCES mail_messages(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS mail_message_parts (
            message_id TEXT NOT NULL,
            part_id TEXT NOT NULL,
            attachment_id TEXT CHECK(
                attachment_id IS NULL OR attachment_id GLOB '{MAIL_ATTACHMENT_ID_PREFIX}*'
            ),
            mime_type TEXT NOT NULL,
            filename TEXT,
            is_inline INTEGER NOT NULL CHECK(is_inline IN (0, 1)),
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            attachment_remote_spec_json TEXT,
            PRIMARY KEY(message_id, part_id),
            FOREIGN KEY(message_id) REFERENCES mail_messages(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_message_parts_attachment_id
            ON mail_message_parts(attachment_id)
            WHERE attachment_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS mail_folder_backfill_state (
            folder_id TEXT PRIMARY KEY NOT NULL,
            checkpoint_json TEXT,
            last_backfill_at_ms INTEGER,
            FOREIGN KEY(folder_id) REFERENCES mail_folders(id) ON DELETE CASCADE
        );
        """,
    )
