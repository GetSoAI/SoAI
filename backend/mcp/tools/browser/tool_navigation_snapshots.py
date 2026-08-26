"""SoAI - Browser navigation snapshot payloads [backend/mcp/tools/browser/tool_navigation_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.browser.snapshot_capture import capture_page_snapshot_with_timeout
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "attach_inline_snapshot_payload",
    "capture_inline_snapshot_payload",
    "format_inline_snapshot_payload",
)

OPERATION_MCP_BROWSER_TOOL_NAVIGATION_SNAPSHOTS_CAPTURE_INLINE = (
    "mcp.browser.tool_navigation_snapshots.capture_inline_snapshot_payload"
)

LOGGER_NAME = "SoAI.mcp.tools.tool_navigation_snapshots"


def format_inline_snapshot_payload(
    snapshot_text: str,
    refs: list[JSONDict],
    *,
    max_chars: int,
) -> JSONDict:
    total_chars = len(snapshot_text)
    truncated = total_chars > max_chars
    next_start_char = max_chars if truncated else None
    remaining_chars = max(0, total_chars - (next_start_char or total_chars))
    output_text = snapshot_text
    if truncated:
        output_text = f"{snapshot_text[:max_chars].rstrip()}\n…"
    return {
        "snapshot": output_text,
        "refs": refs,
        "truncated": truncated,
        "total_chars": total_chars,
        "returned_start_char": 0,
        "next_start_char": next_start_char,
        "remaining_chars": remaining_chars,
    }


async def capture_inline_snapshot_payload(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    roles: tuple[str, ...] | None,
) -> JSONDict:
    snapshot_action_timeout_sec = resolve_action_timeout_sec(utility_tools)
    try:
        snapshot_text, refs, max_chars = await capture_page_snapshot_with_timeout(
            utility_tools=utility_tools,
            state=state,
            page=page,
            action_timeout_sec=float(snapshot_action_timeout_sec),
            roles=roles,
        )
    except MCPToolError:
        return {"snapshot_error": "Browser snapshot is unavailable."}
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_BROWSER_TOOL_NAVIGATION_SNAPSHOTS_CAPTURE_INLINE,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to capture inline browser snapshot (non-critical).",
            operation=OPERATION_MCP_BROWSER_TOOL_NAVIGATION_SNAPSHOTS_CAPTURE_INLINE,
            details={},
            level="warning",
        )
        return {"snapshot_error": "Browser snapshot is unavailable."}
    return format_inline_snapshot_payload(snapshot_text, refs, max_chars=max_chars)


async def attach_inline_snapshot_payload(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    result: JSONDict,
    *,
    include_snapshot: bool,
    roles: tuple[str, ...] | None,
) -> None:
    if not include_snapshot:
        return
    payload = await capture_inline_snapshot_payload(
        utility_tools,
        state,
        page,
        roles=roles,
    )
    result.update(payload)
