"""SoAI - Browser tool: browser_snapshot [backend/mcp/tools/browser/tool_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.browser.page_metadata import safe_page_title
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    prepare_snapshot_refs,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.snapshot_capture import (
    capture_page_snapshot_with_timeout,
    parse_snapshot_roles,
    resolve_snapshot_max_chars,
)
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_snapshot",)


async def tool_browser_snapshot(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    allowed = BROWSER_SESSION_PARAM_KEYS.union({"start_char", "snapshot_roles"})
    require_allowed_keys(
        arguments,
        allowed_keys=allowed,
        tool_name="browser_snapshot",
    )
    start_char = parse_optional_int_strict(
        arguments.get("start_char"),
        field_name="start_char",
        min_value=0,
        max_value=10_000_000,
    )
    roles = parse_snapshot_roles(arguments.get("snapshot_roles"), field_name="snapshot_roles")
    requested_start_char = 0 if start_char is None else start_char
    if roles is not None and requested_start_char > 0:
        raise MCPToolError(
            -32602,
            "start_char pagination is not supported when snapshot_roles filtering is enabled. Omit snapshot_roles or omit start_char.",
        )
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    async with browser_action_lock(state):
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page = require_current_page(state)
            output_url = await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_snapshot",
            )
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
            max_chars = resolve_snapshot_max_chars(utility_tools)

            if (
                requested_start_char > 0
                and roles is None
                and state.ref_page_url == page.url
                and state.last_snapshot_text is not None
            ):
                full_text = state.last_snapshot_text
                returned_start_char = min(requested_start_char, len(full_text))
                snapshot_text = full_text[returned_start_char:]
                truncated = len(snapshot_text) > max_chars
                next_start_char = returned_start_char + max_chars if truncated else None
                remaining_chars = max(0, len(full_text) - (next_start_char or len(full_text)))
                if truncated:
                    snapshot_text = f"{snapshot_text[:max_chars].rstrip()}\n…"
                return {
                    "snapshot": snapshot_text,
                    "refs": [],
                    "truncated": truncated,
                    "url": output_url,
                    "total_chars": len(full_text),
                    "returned_start_char": returned_start_char,
                    "next_start_char": next_start_char,
                    "remaining_chars": remaining_chars,
                    "title": await safe_page_title(
                        page,
                        timeout_ms=int(action_timeout_sec) * 1000,
                        retries=1,
                        delay_ms=0,
                    ),
                }

            prepare_snapshot_refs(state)
            snapshot_text, refs, max_chars = await capture_page_snapshot_with_timeout(
                utility_tools=utility_tools,
                state=state,
                page=page,
                action_timeout_sec=float(action_timeout_sec),
                roles=roles,
            )
            total_chars = len(snapshot_text)
            returned_start_char = 0
            truncated = total_chars > max_chars
            next_start_char = max_chars if truncated else None
            remaining_chars = max(0, total_chars - (next_start_char or total_chars))
            output_text = snapshot_text
            if truncated:
                output_text = f"{snapshot_text[:max_chars].rstrip()}\n…"

            output_url = await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_snapshot",
            )
            title_timeout_ms = int(action_timeout_sec) * 1000
            return {
                "snapshot": output_text,
                "refs": refs,
                "truncated": truncated,
                "url": output_url,
                "total_chars": total_chars,
                "returned_start_char": returned_start_char,
                "next_start_char": next_start_char,
                "remaining_chars": remaining_chars,
                "title": await safe_page_title(
                    page,
                    timeout_ms=title_timeout_ms,
                    retries=1,
                    delay_ms=0,
                ),
            }
