"""SoAI - Mail MCP tool definitions [backend/mcp/mail/tool_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.shared.tool_annotations import build_tool_annotation_profiles
from mcp.shared.tool_definitions import build_tool_definition
from mcp.tools.icons import ICON_MAIL

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_mail_tool_definitions",)


def build_mail_tool_definitions() -> dict[str, JSONDict]:
    read_only_annotations, sync_annotations, destructive_annotations = (
        build_tool_annotation_profiles()
    )
    folder_list_properties: dict[str, JSONValue] = {
        "account_id": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1},
        "cursor": {"type": "string"},
        "order_by": {"type": "string", "enum": ["name", "unread_count", "message_count"]},
        "order_direction": {"type": "string", "enum": ["asc", "desc"]},
    }
    message_list_properties: dict[str, JSONValue] = {
        "folder_id": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1},
        "cursor": {"type": "string"},
        "order_by": {
            "type": "string",
            "enum": ["received_at_ms", "sent_at_ms", "subject", "from", "size_bytes"],
        },
        "order_direction": {"type": "string", "enum": ["asc", "desc"]},
        "query": {"type": "string"},
        "thread_id": {"type": "string"},
        "unread": {"type": "boolean"},
        "flagged": {"type": "boolean"},
        "has_attachments": {"type": "boolean"},
        "from": {"type": "string"},
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "since_ms": {"type": "integer"},
        "before_ms": {"type": "integer"},
    }
    return {
        "mail_accounts_list": _build_definition(
            title="Mail Accounts List",
            description="List configured mail accounts for the authenticated user.",
            icon_src=ICON_MAIL,
            properties={},
            required=(),
            annotations=read_only_annotations,
        ),
        "mail_folders_list": _build_definition(
            title="Mail Folders List",
            description="List cached folders for one mail account.",
            icon_src=ICON_MAIL,
            properties=folder_list_properties,
            required=("account_id",),
            annotations=read_only_annotations,
        ),
        "mail_messages_list": _build_definition(
            title="Mail Messages List",
            description="List cached mail messages for one folder using cache-first filters.",
            icon_src=ICON_MAIL,
            properties=message_list_properties,
            required=("folder_id",),
            annotations=read_only_annotations,
        ),
        "mail_message_read": _build_definition(
            title="Mail Message Read",
            description="Read one cached mail message with standard chunked-read arguments.",
            icon_src=ICON_MAIL,
            properties={
                "message_id": {"type": "string"},
                "part_id": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "default": 50000},
                "offset_chars": {"type": "integer", "minimum": 0, "default": 0},
            },
            required=("message_id",),
            annotations=read_only_annotations,
        ),
        "mail_attachment_download": _build_definition(
            title="Mail Attachment Download",
            description="Persist one mail attachment into SoAI files storage.",
            icon_src=ICON_MAIL,
            properties={"attachment_id": {"type": "string"}},
            required=("attachment_id",),
            annotations=read_only_annotations,
        ),
        "mail_account_sync": _build_definition(
            title="Mail Account Sync",
            description="Run an explicit cache refresh for one mail account.",
            icon_src=ICON_MAIL,
            properties={"account_id": {"type": "string"}, "folder_id": {"type": "string"}},
            required=("account_id",),
            annotations=sync_annotations,
        ),
        "mail_messages_remote_search": _build_definition(
            title="Mail Messages Remote Search",
            description="Run an explicit remote search and import matching summaries into cache.",
            icon_src=ICON_MAIL,
            properties={
                "account_id": {"type": "string"},
                "folder_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
                "from": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "since_ms": {"type": "integer"},
                "before_ms": {"type": "integer"},
                "text": {"type": "string"},
                "rfc822_message_id": {"type": "string"},
            },
            required=("account_id",),
            annotations=sync_annotations,
        ),
        "mail_folder_backfill": _build_definition(
            title="Mail Folder Backfill",
            description="Import the next older cache batch for one folder.",
            icon_src=ICON_MAIL,
            properties={
                "folder_id": {"type": "string"},
                "batch_limit": {"type": "integer", "minimum": 1},
                "before_ms": {"type": "integer"},
            },
            required=("folder_id",),
            annotations=sync_annotations,
        ),
        "mail_message_compose": _build_definition(
            title="Mail Message Compose",
            description="Compose and send or save a draft message for one mail account.",
            icon_src=ICON_MAIL,
            properties={
                "account_id": {"type": "string"},
                "mode": {"type": "string", "enum": ["new", "reply", "reply_all", "forward"]},
                "delivery": {"type": "string", "enum": ["send", "save_draft"]},
                "base_message_id": {"type": "string"},
                "to": {"type": "array", "items": {"type": "object"}},
                "cc": {"type": "array", "items": {"type": "object"}},
                "bcc": {"type": "array", "items": {"type": "object"}},
                "subject": {"type": "string"},
                "body_text": {"type": "string"},
                "body_html": {"type": "string"},
                "attachments": {"type": "array", "items": {"type": "object"}},
            },
            required=("account_id", "mode", "delivery", "subject", "body_text"),
            annotations=destructive_annotations,
        ),
        "mail_message_update": _build_definition(
            title="Mail Message Update",
            description="Apply a mailbox mutation to one cached mail message.",
            icon_src=ICON_MAIL,
            properties={
                "message_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": [
                        "mark_read",
                        "mark_unread",
                        "flag",
                        "unflag",
                        "archive",
                        "unarchive",
                        "move",
                        "copy",
                        "delete",
                        "restore",
                    ],
                },
                "destination_folder_id": {"type": "string"},
            },
            required=("message_id", "action"),
            annotations=destructive_annotations,
        ),
        "mail_folder_update": _build_definition(
            title="Mail Folder Update",
            description="Create, rename, delete, or change subscription state for one folder.",
            icon_src=ICON_MAIL,
            properties={
                "account_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["create", "rename", "delete", "subscribe", "unsubscribe"],
                },
                "folder_id": {"type": "string"},
                "folder_name": {"type": "string"},
            },
            required=("account_id", "action"),
            annotations=destructive_annotations,
        ),
    }


def _build_definition(
    *,
    title: str,
    description: str,
    icon_src: str,
    properties: dict[str, JSONValue],
    required: tuple[str, ...],
    annotations: dict[str, bool],
) -> JSONDict:
    return build_tool_definition(
        title=title,
        description=description,
        icon_src=icon_src,
        properties=properties,
        required=required,
        annotations=annotations,
    )
