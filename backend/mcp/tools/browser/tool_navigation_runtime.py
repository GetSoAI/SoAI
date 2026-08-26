"""SoAI - Browser navigation runtime state helpers [backend/mcp/tools/browser/tool_navigation_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp.tools.browser.download_storage import ensure_download_paths
from mcp.tools.browser.download_support import downloads_to_dicts
from mcp.tools.browser.navigation_block_detection import (
    apply_navigation_block_detection,
)
from mcp.tools.browser.page_metadata import safe_page_title
from mcp.tools.browser.page_ref_state import transfer_active_page_ref_state
from mcp.tools.browser.page_title_config import (
    resolve_title_retry_attempts,
    resolve_title_retry_delay_ms,
)
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import require_current_page
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.storage_state import persist_synced_browser_action_storage_state
from mcp.tools.browser.tool_navigation_snapshots import capture_inline_snapshot_payload
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "build_navigation_result",
    "build_persisted_navigation_result_with_media",
    "build_navigation_result_with_media",
    "complete_navigation_action",
    "read_navigation_page",
    "refresh_navigation_page",
    "run_post_navigation",
)


async def read_navigation_page(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    desired_tab_id: int | None = None,
) -> tuple[str, Page]:
    downloads_dir = ensure_download_paths(utility_tools, state).downloads_dir
    await sync_session_state(
        utility_tools.config,
        state,
        downloads_dir=downloads_dir,
    )
    if desired_tab_id is not None:
        if desired_tab_id < 0 or desired_tab_id >= len(state.pages):
            raise MCPToolError(
                -32602,
                f"Invalid tab_id: {desired_tab_id}",
                data={"total_tabs": len(state.pages)},
            )
        outgoing_page = require_current_page(state)
        target_page = state.pages[desired_tab_id]
        transfer_active_page_ref_state(
            state,
            outgoing_page=outgoing_page,
            incoming_page=target_page,
            reload_incoming=True,
        )
        state.active_index = int(desired_tab_id)
    return downloads_dir, require_current_page(state)


async def refresh_navigation_page(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    downloads_dir: str,
    navigated_page: Page,
) -> Page:
    await sync_session_state(
        utility_tools.config,
        state,
        downloads_dir=downloads_dir,
        desired_active_page=navigated_page,
    )
    return require_current_page(state)


async def complete_navigation_action(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    downloads_dir: str,
    stabilize_ms: int,
) -> Page:
    if stabilize_ms:
        await page.wait_for_timeout(stabilize_ms)
    async with state.lock:
        return await refresh_navigation_page(
            utility_tools,
            state,
            downloads_dir=downloads_dir,
            navigated_page=page,
        )


async def run_post_navigation(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    downloads_dir: str,
    stabilize_ms: int,
    tool_name: str,
    on_locked_page: Callable[[Page], Awaitable[JSONDict]],
) -> JSONDict:
    refreshed_page = await complete_navigation_action(
        utility_tools,
        state,
        page,
        downloads_dir=downloads_dir,
        stabilize_ms=stabilize_ms,
    )
    async with state.lock:
        await require_browser_page_output_allowed(
            utility_tools,
            refreshed_page,
            tool_name=tool_name,
        )
        return await on_locked_page(refreshed_page)


async def build_navigation_result(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    title_timeout_ms: int,
    include_snapshot: bool,
    snapshot_roles: tuple[str, ...] | None,
) -> JSONDict:
    output_url = await require_browser_page_output_allowed(
        utility_tools,
        page,
        tool_name="browser_navigate",
    )
    result: JSONDict = {
        "url": output_url,
        "title": await safe_page_title(
            page,
            timeout_ms=title_timeout_ms,
            retries=resolve_title_retry_attempts(utility_tools.config),
            delay_ms=resolve_title_retry_delay_ms(utility_tools.config),
        ),
    }
    downloads_dir = state.downloads_dir
    if isinstance(downloads_dir, str) and downloads_dir.strip():
        result["downloads_dir"] = downloads_dir
        result["downloads"] = downloads_to_dicts(state.downloads)
    apply_navigation_block_detection(result, state)
    if include_snapshot:
        result.update(
            await capture_inline_snapshot_payload(
                utility_tools,
                state,
                page,
                roles=snapshot_roles,
            ),
        )
    return result


async def build_navigation_result_with_media(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    title_timeout_ms: int,
    include_snapshot: bool,
    snapshot_roles: tuple[str, ...] | None,
    screenshot_payload: JSONDict | None,
    screenshot_error: str | None,
) -> JSONDict:
    result = await build_navigation_result(
        utility_tools,
        state,
        page,
        title_timeout_ms=title_timeout_ms,
        include_snapshot=include_snapshot,
        snapshot_roles=snapshot_roles,
    )
    if screenshot_payload is not None:
        result["screenshot"] = screenshot_payload
    if screenshot_error is not None:
        result["screenshot_error"] = screenshot_error
    return result


async def build_persisted_navigation_result_with_media(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    title_timeout_ms: int,
    include_snapshot: bool,
    snapshot_roles: tuple[str, ...] | None,
    screenshot_payload: JSONDict | None,
    screenshot_error: str | None,
    persist_reason: str,
) -> JSONDict:
    result = await build_navigation_result_with_media(
        utility_tools,
        state,
        page,
        title_timeout_ms=title_timeout_ms,
        include_snapshot=include_snapshot,
        snapshot_roles=snapshot_roles,
        screenshot_payload=screenshot_payload,
        screenshot_error=screenshot_error,
    )
    await persist_synced_browser_action_storage_state(
        utility_tools=utility_tools,
        state=state,
        reason=persist_reason,
    )
    return result
