"""SoAI - Mail MCP resource catalog definitions [backend/mcp/mail/resource_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry
from mcp.mail.resource_uris import MAIL_RESOURCE_URI
from mcp.tools.icons import ICON_MAIL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_mail_resource_metadata",
    "build_mail_resource_templates",
)


def build_mail_resource_templates() -> tuple[JSONDict, ...]:
    return (
        {
            "uriTemplate": "soai://mail/messages/{message_id}?max_chars={max_chars}&offset_chars={offset_chars}&part_id={part_id}",
            "name": "Mail Message",
            "title": "Mail Message",
            "description": "Read one cached mail message with standard chunked-read parameters.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_MAIL, include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.8},
        },
        {
            "uriTemplate": "soai://mail/folders/{folder_id}/head?limit={limit}&order_by={order_by}&order_direction={order_direction}&query={query}",
            "name": "Mail Folder Head",
            "title": "Mail Folder Head",
            "description": "List cached messages for one folder using the same filters as mail_messages_list.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_MAIL, include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.7},
        },
    )


def build_mail_resource_metadata() -> JSONDict:
    return {
        MAIL_RESOURCE_URI: {
            "name": "Mail Accounts",
            "title": "Mail Accounts",
            "description": "List configured mail accounts for the authenticated user.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_MAIL)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.8},
        },
    }
