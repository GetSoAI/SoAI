"""SoAI - Browser navigation tool result assembly [backend/mcp/tools/browser/navigation_result_assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.navigation_capture import capture_navigation_screenshot
from mcp.tools.browser.tool_navigation_runtime import (
    build_persisted_navigation_result_with_media,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict, JSONObject
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "NavigationResultPlan",
    "build_captured_navigation_result",
)

NAVIGATION_PERSIST_REASON = "browser_navigate"


@dataclass(frozen=True, slots=True)
class NavigationResultPlan:
    title_timeout_ms: int
    include_snapshot: bool
    snapshot_roles: tuple[str, ...] | None
    screenshot_operation: str
    screenshot_failure_message: str
    screenshot_skip_reason: str | None
    extra_fields: JSONObject


async def _resolve_navigation_screenshot(
    page: Page,
    plan: NavigationResultPlan,
) -> tuple[JSONDict | None, str | None]:
    skip_reason = plan.screenshot_skip_reason
    if skip_reason is not None:
        return (None, skip_reason)
    return await capture_navigation_screenshot(
        page=page,
        timeout_ms=plan.title_timeout_ms,
        operation=plan.screenshot_operation,
        failure_message=plan.screenshot_failure_message,
    )


async def build_captured_navigation_result(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    plan: NavigationResultPlan,
) -> JSONDict:
    screenshot_payload, screenshot_error = await _resolve_navigation_screenshot(page, plan)
    result = await build_persisted_navigation_result_with_media(
        utility_tools,
        state,
        page,
        title_timeout_ms=plan.title_timeout_ms,
        include_snapshot=plan.include_snapshot,
        snapshot_roles=plan.snapshot_roles,
        screenshot_payload=screenshot_payload,
        screenshot_error=screenshot_error,
        persist_reason=NAVIGATION_PERSIST_REASON,
    )
    result.update(plan.extra_fields)
    return result
