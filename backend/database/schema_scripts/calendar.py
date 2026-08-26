"""SoAI - Database schema for calendar accounts and cache [backend/database/schema_scripts/calendar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.account_identifiers import (
    CALENDAR_ACCOUNT_ID_PREFIX,
    CALENDAR_CALENDAR_ID_PREFIX,
    CALENDAR_EVENT_ID_PREFIX,
    CALENDAR_REMINDER_ID_PREFIX,
)
from database.sql.script import execute_sql_script

__all__ = ("apply_calendar_schema",)


def apply_calendar_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS calendar_accounts (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{CALENDAR_ACCOUNT_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            external_account_id TEXT NOT NULL UNIQUE,
            caldav_base_url TEXT NOT NULL,
            discovered_principal_json TEXT,
            linked_mail_account_id TEXT,
            last_sync_at_ms INTEGER,
            last_sync_error TEXT,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(external_account_id) REFERENCES external_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY(linked_mail_account_id) REFERENCES mail_accounts(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_calendar_accounts_user_created
            ON calendar_accounts(user_id, created_at_ms DESC, id DESC);
        CREATE TABLE IF NOT EXISTS calendar_calendars (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{CALENDAR_CALENDAR_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            calendar_account_id TEXT NOT NULL,
            remote_href TEXT NOT NULL,
            sync_token TEXT,
            etag TEXT,
            name TEXT NOT NULL,
            color TEXT,
            timezone TEXT,
            read_only INTEGER NOT NULL CHECK(read_only IN (0, 1)),
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(calendar_account_id) REFERENCES calendar_accounts(id) ON DELETE CASCADE,
            UNIQUE(calendar_account_id, remote_href)
        );
        CREATE INDEX IF NOT EXISTS idx_calendar_calendars_account_name
            ON calendar_calendars(calendar_account_id, name COLLATE NOCASE, id DESC);
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{CALENDAR_EVENT_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            calendar_id TEXT NOT NULL,
            remote_href TEXT NOT NULL,
            etag TEXT,
            uid TEXT,
            summary TEXT NOT NULL,
            description TEXT,
            location TEXT,
            start_at_ms INTEGER NOT NULL,
            end_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL,
            timezone TEXT,
            all_day INTEGER NOT NULL CHECK(all_day IN (0, 1)),
            organizer_json TEXT,
            attendee_count INTEGER NOT NULL CHECK(attendee_count >= 0),
            attendees_json TEXT,
            has_alarms INTEGER NOT NULL CHECK(has_alarms IN (0, 1)),
            recurrence_json TEXT,
            alarms_json TEXT,
            raw_ics TEXT,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(calendar_id) REFERENCES calendar_calendars(id) ON DELETE CASCADE,
            UNIQUE(calendar_id, remote_href)
        );
        CREATE INDEX IF NOT EXISTS idx_calendar_events_calendar_start
            ON calendar_events(calendar_id, start_at_ms ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_calendar_updated
            ON calendar_events(calendar_id, updated_at_ms DESC, id DESC);
        CREATE TABLE IF NOT EXISTS calendar_sync_windows (
            calendar_id TEXT NOT NULL,
            window_start_ms INTEGER NOT NULL,
            window_end_ms INTEGER NOT NULL,
            synced_at_ms INTEGER NOT NULL,
            synced_window_start_ms INTEGER NOT NULL,
            synced_window_end_ms INTEGER NOT NULL,
            PRIMARY KEY(calendar_id, window_start_ms, window_end_ms),
            FOREIGN KEY(calendar_id) REFERENCES calendar_calendars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS calendar_reminders (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{CALENDAR_REMINDER_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            calendar_account_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            occurrence_key TEXT NOT NULL,
            alarm_key TEXT NOT NULL,
            response_state TEXT NOT NULL,
            remind_at_ms INTEGER NOT NULL,
            due_at_ms INTEGER NOT NULL,
            delivered_at_ms INTEGER,
            dismissed_at_ms INTEGER,
            created_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(calendar_account_id) REFERENCES calendar_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY(event_id) REFERENCES calendar_events(id) ON DELETE CASCADE,
            UNIQUE(
                user_id,
                calendar_account_id,
                event_id,
                occurrence_key,
                alarm_key,
                response_state
            )
        );
        CREATE INDEX IF NOT EXISTS idx_calendar_reminders_user_due
            ON calendar_reminders(user_id, remind_at_ms ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_calendar_reminders_account_due
            ON calendar_reminders(calendar_account_id, remind_at_ms ASC, id ASC);
        """,
    )
