"""SoAI - MCP utility tool definitions: browser navigation [backend/mcp/tools/utility_tool_definitions/browser_navigation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_GLOBE
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_schema,
    nullable_boolean_schema,
    nullable_integer_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_action_input_schema,
    build_browser_session_param_properties,
)
from mcp.tools.utility_tool_definitions.browser_snapshot_schema_primitives import (
    build_downloads_output_properties,
    build_snapshot_payload_properties,
)
from mcp.tools.utility_tool_definitions.browser_tool_input_schema_primitives import (
    build_inline_snapshot_input_properties,
    build_timeout_ms_property,
    build_wait_until_property,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_navigation_tool_definitions",)


def build_browser_navigation_tool_definitions() -> dict[str, JSONDict]:
    navigate_icons = [build_tool_icon_entry(ICON_GLOBE)]
    session_params = build_browser_session_param_properties()
    output_properties: JSONDict = {
        "url": {"type": "string"},
        "title": {"type": "string"},
        **build_downloads_output_properties(),
        **build_snapshot_payload_properties(),
        "screenshot": {
            "type": "object",
            "properties": {
                "content_type": {"type": "string"},
                "image_base64": {"type": "string"},
            },
        },
        "screenshot_error": {"type": "string"},
        "download_started": {"type": "boolean"},
        "blocked": {"type": "boolean"},
        "blocked_reason": {"type": "string"},
        "blocked_evidence": {
            "type": "object",
            "properties": {
                "match": {"type": "string"},
                "value": {},
                "url": {"type": "string"},
                "redirected": {"type": "boolean"},
                "snippet": {"type": "string"},
            },
        },
        "recovery_hints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "browser_downloads_hint": {"type": "string"},
        "browser_downloads_args": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "session_scope": {"type": "string"},
            },
        },
    }
    output_schema: JSONDict = {"type": "object", "properties": output_properties}
    output_properties["navigated"] = {"type": "boolean"}
    output_properties["reason"] = {"type": "string"}
    output_properties["direction"] = {"type": "string"}
    return {
        "browser_navigate": {
            "title": "Browser Navigate",
            "description": "Navigate a tab to a URL or move backward or forward through the active tab history. Set action=url with url, or action=back/forward without URL-only options. History actions require an active browser session. Requires TOOLS.MCP.BROWSER.ENABLED=true. Network navigation is blocked when SYSTEM.RUNTIME.STAY_OFFLINE=true.",
            "icons": navigate_icons,
            "input_schema": build_browser_action_input_schema(
                actions=("url", "back", "forward"),
                action_description="url requires url; back/forward reject URL-only options.",
                session_params=session_params,
                extra_properties={
                    "url": non_empty_string_schema(),
                    "tab_id": nullable_integer_schema(
                        minimum=0,
                        maximum=1000,
                        description="Optional tab id (0-based) from browser_tabs action=list. When provided, the tool switches that tab active before navigating.",
                    ),
                    "accept_insecure": nullable_boolean_schema(
                        description="If set, recreate the browser context to enable/disable ignoring TLS certificate errors for https URLs.",
                    ),
                    **build_wait_until_property(),
                    **build_timeout_ms_property(
                        min_ms=1,
                        max_ms=300_000,
                        description="Navigation timeout in milliseconds.",
                    ),
                    "http_auth": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "properties": {
                            "secret_handle": nullable_non_empty_string_schema(),
                            "credential_id": nullable_non_empty_string_schema(),
                        },
                        "description": "Optional HTTP Basic Auth credentials applied at the browser context level (requires recreating the context). Provide exactly one of secret_handle or credential_id.",
                    },
                    "clear_http_auth": nullable_boolean_schema(
                        description="If true, recreate the browser context without any HTTP Basic Auth credentials.",
                    ),
                    **build_inline_snapshot_input_properties(),
                },
            ),
            "output_schema": output_schema,
            "annotations": build_tool_annotation_flags(open_world=True),
        },
    }
