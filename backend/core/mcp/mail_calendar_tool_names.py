"""SoAI - Mail and calendar MCP tool name constants [backend/core/mcp/mail_calendar_tool_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

MAIL_CALENDAR_MCP_TOOL_NAMES: tuple[str, ...] = (
    "mail_accounts_list",
    "mail_folders_list",
    "mail_messages_list",
    "mail_message_read",
    "mail_attachment_download",
    "mail_account_sync",
    "mail_messages_remote_search",
    "mail_folder_backfill",
    "mail_message_compose",
    "mail_message_update",
    "mail_folder_update",
    "calendar_accounts_list",
    "calendar_calendars_list",
    "calendar_account_sync",
    "calendar_window_sync",
    "calendar_events_list",
    "calendar_event_read",
    "calendar_event_update",
    "calendar_invite_respond",
)
