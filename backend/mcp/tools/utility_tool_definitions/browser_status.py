"""SoAI - MCP utility tool definitions: browser_status [backend/mcp/tools/utility_tool_definitions/browser_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_STATUS
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_input_schema,
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_status_tool_definitions",)


def build_browser_status_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_STATUS)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_status": {
            "title": "Browser Status",
            "description": (
                "Return the current browser session status, including active tab metadata, "
                "dialog and log counters, persistence mode, and storage_state health. If no "
                "session exists, return disconnected status and instruct the caller to call "
                "browser_navigate first."
            ),
            "icons": icons,
            "input_schema": build_browser_session_input_schema(session_params=session_params),
            "output_schema": {
                "type": "object",
                "properties": {
                    "session_available": {"type": "boolean"},
                    "profile": {"type": "string"},
                    "session_scope": {"type": "string"},
                    "owner_key": {"type": "string"},
                    "persistence_mode": {"type": ["string", "null"]},
                    "user_data_dir": {"type": ["string", "null"]},
                    "connected": {"type": "boolean"},
                    "tabs_count": {"type": "integer"},
                    "active_tab_id": {"type": ["integer", "null"]},
                    "active_url": {"type": ["string", "null"]},
                    "active_title": {"type": ["string", "null"]},
                    "dialogs_pending": {"type": "integer"},
                    "console_messages": {"type": "integer"},
                    "network_requests": {"type": "integer"},
                    "storage_state": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "path": {"type": ["string", "null"]},
                            "dirty": {"type": "boolean"},
                            "last_saved_age_sec": {"type": ["number", "null"]},
                            "last_error": {"type": ["string", "null"]},
                        },
                    },
                    "next_action": {"type": "string"},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
