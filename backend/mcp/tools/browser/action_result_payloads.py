"""SoAI - Browser tool action result payloads [backend/mcp/tools/browser/action_result_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json import JSONDict
from mcp.tools.browser.download_support import downloads_to_dicts
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import mark_page_load
from mcp.tools.browser.storage_state import (
    persist_synced_browser_action_storage_state,
    sync_browser_action_state,
)
from mcp.tools.browser.tool_navigation_snapshots import attach_inline_snapshot_payload

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.browser.action_preflight import BrowserActionPagePreflight
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "BrowserActionSuccessFlag",
    "BrowserInlineSnapshotRequest",
    "build_action_result_payload",
    "build_action_success_payload",
)


@dataclass(frozen=True, slots=True)
class BrowserInlineSnapshotRequest:
    include_snapshot: bool
    snapshot_roles: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class BrowserActionSuccessFlag:
    key: str
    value: bool


async def build_action_result_payload(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    downloads_dir: str,
    reason: str,
    url_before: str,
    include_snapshot: bool,
    snapshot_roles: tuple[str, ...] | None,
    success_key: str,
    success_value: bool,
) -> JSONDict:
    await sync_browser_action_state(
        utility_tools=utility_tools,
        state=state,
        downloads_dir=downloads_dir,
    )
    url_after = await require_browser_page_output_allowed(
        utility_tools,
        page,
        tool_name=reason,
    )
    await persist_synced_browser_action_storage_state(
        utility_tools=utility_tools,
        state=state,
        reason=reason,
    )
    url_changed = url_after != url_before
    if url_changed:
        mark_page_load(state)
    result: JSONDict = {
        success_key: success_value,
        "url": url_after,
        "url_changed": url_changed,
        "downloads_dir": downloads_dir,
        "downloads": downloads_to_dicts(state.downloads),
    }
    await attach_inline_snapshot_payload(
        utility_tools,
        state,
        page,
        result,
        include_snapshot=include_snapshot,
        roles=snapshot_roles,
    )
    return result


async def build_action_success_payload(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    preflight: BrowserActionPagePreflight,
    reason: str,
    snapshot: BrowserInlineSnapshotRequest,
    success: BrowserActionSuccessFlag,
) -> JSONDict:
    return await build_action_result_payload(
        utility_tools,
        state,
        preflight.page,
        downloads_dir=preflight.downloads_dir,
        reason=reason,
        url_before=preflight.url_before,
        include_snapshot=bool(snapshot.include_snapshot),
        snapshot_roles=snapshot.snapshot_roles,
        success_key=str(success.key),
        success_value=bool(success.value),
    )
