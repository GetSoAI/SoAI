"""SoAI - MCP utility tool definitions: browser_profiles [backend/mcp/tools/utility_tool_definitions/browser_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_PROFILES

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_profiles_tool_definitions",)


def build_browser_profiles_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_PROFILES)]
    return {
        "browser_profiles": {
            "title": "Browser Profiles",
            "description": (
                "List configured browser profiles, including whether each profile uses remote CDP "
                "or local persistence settings."
            ),
            "icons": icons,
            "input_schema": {"type": "object", "additionalProperties": False, "properties": {}},
            "output_schema": {
                "type": "object",
                "properties": {
                    "default_profile": {"type": "string"},
                    "default_session_scope": {"type": "string"},
                    "profiles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "has_remote_cdp": {"type": "boolean"},
                                "cdp_url": {"type": "string"},
                                "persistence_mode": {"type": "string"},
                                "headless": {"type": ["boolean", "null"]},
                                "channel": {"type": ["string", "null"]},
                                "locale": {"type": ["string", "null"]},
                                "timezone_id": {"type": ["string", "null"]},
                                "accept_language": {"type": ["string", "null"]},
                                "viewport_width": {"type": ["integer", "null"]},
                                "viewport_height": {"type": ["integer", "null"]},
                                "device_scale_factor": {"type": ["number", "null"]},
                            },
                        },
                    },
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
