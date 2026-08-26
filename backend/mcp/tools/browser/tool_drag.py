"""SoAI - Browser tool: browser_drag [backend/mcp/tools/browser/tool_drag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import (
    optional_non_empty_string,
    require_allowed_keys,
)
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.browser.html5_drag_events import (
    cleanup_drag_probe,
    dispatch_html5_drag_fallback,
    drag_probe_drop_count,
    empty_drag_probe_counts,
    install_drag_probe,
    is_html5_draggable,
    read_drag_probe_counts,
)
from mcp.tools.browser.ref_lookup import locator_by_ref, optional_ref
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import (
    finalize_locked_browser_action,
    locked_browser_action_page,
)
from mcp.tools.browser.timeouts import action_timeout_scope
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_drag",)


async def _resolve_unique_selector_locator(
    page: Page,
    *,
    selector: str,
    match_index: int | None,
    selector_field: str,
    ref_field: str,
    match_index_field: str,
) -> Locator:
    locator = page.locator(selector)
    count = await locator.count()
    if int(count) == 0:
        raise MCPToolError(-32602, f"{selector_field} selector did not match any elements.")
    if match_index is None:
        if int(count) != 1:
            raise MCPToolError(
                -32602,
                (
                    f"{selector_field} selector matched {int(count)} elements. "
                    f"Refine the selector, use {ref_field} from browser_snapshot, "
                    f"or provide {match_index_field}."
                ),
            )
        return locator.first
    if match_index < 0 or match_index >= int(count):
        raise MCPToolError(
            -32602,
            f"{match_index_field} is out of range.",
            data={"matches": int(count)},
        )
    return locator.nth(int(match_index))


async def tool_browser_drag(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "element_from",
                "from_ref",
                "from_selector",
                "from_match_index",
                "element_to",
                "to_ref",
                "to_selector",
                "to_match_index",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_drag",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    _ = optional_non_empty_string(arguments.get("element_from"), key="element_from")
    _ = optional_non_empty_string(arguments.get("element_to"), key="element_to")
    from_ref = optional_ref(arguments, key="from_ref")
    to_ref = optional_ref(arguments, key="to_ref")
    from_selector = optional_non_empty_string(
        arguments.get("from_selector"),
        key="from_selector",
    )
    to_selector = optional_non_empty_string(
        arguments.get("to_selector"),
        key="to_selector",
    )
    from_match_index = parse_optional_int_strict(
        arguments.get("from_match_index"),
        field_name="from_match_index",
        min_value=0,
        max_value=100_000,
    )
    to_match_index = parse_optional_int_strict(
        arguments.get("to_match_index"),
        field_name="to_match_index",
        min_value=0,
        max_value=100_000,
    )
    if (from_ref is None) == (from_selector is None):
        raise MCPToolError(-32602, "Provide exactly one of from_ref or from_selector")
    if (to_ref is None) == (to_selector is None):
        raise MCPToolError(-32602, "Provide exactly one of to_ref or to_selector")
    if from_ref is not None and from_match_index is not None:
        raise MCPToolError(
            -32602,
            "from_match_index is only allowed when from_selector is provided",
        )
    if to_ref is not None and to_match_index is not None:
        raise MCPToolError(-32602, "to_match_index is only allowed when to_selector is provided")
    if from_ref is not None and to_ref is not None and from_ref == to_ref:
        raise MCPToolError(-32602, "from_ref and to_ref must be different")
    if from_selector is not None and to_selector is not None and from_selector == to_selector:
        raise MCPToolError(-32602, "from_selector and to_selector must be different")
    async with locked_browser_action_page(utility_tools, state, tool_name="browser_drag") as page:
        if from_ref is not None:
            from_locator = locator_by_ref(state, page, from_ref)
        else:
            if from_selector is None:
                raise MCPToolError(-32602, "from_selector is required when from_ref is omitted")
            from_locator = await _resolve_unique_selector_locator(
                page,
                selector=from_selector,
                match_index=int(from_match_index) if from_match_index is not None else None,
                selector_field="from_selector",
                ref_field="from_ref",
                match_index_field="from_match_index",
            )
        if to_ref is not None:
            to_locator = locator_by_ref(state, page, to_ref)
        else:
            if to_selector is None:
                raise MCPToolError(-32602, "to_selector is required when to_ref is omitted")
            to_locator = await _resolve_unique_selector_locator(
                page,
                selector=to_selector,
                match_index=int(to_match_index) if to_match_index is not None else None,
                selector_field="to_selector",
                ref_field="to_ref",
                match_index_field="to_match_index",
            )
        source_html5_draggable = await is_html5_draggable(from_locator)
        await install_drag_probe(to_locator)
        fallback_used = False
        drop_counts = empty_drag_probe_counts()
        drop_observed = False
        try:
            async with action_timeout_scope(utility_tools, stabilize_ms=0, buffer_sec=30.0):
                await from_locator.drag_to(to_locator, force=True)
                drop_counts = await read_drag_probe_counts(to_locator)
                drop_observed = drag_probe_drop_count(drop_counts) > 0
                if source_html5_draggable and not drop_observed:
                    fallback_used = await dispatch_html5_drag_fallback(
                        from_locator,
                        to_locator,
                    )
                    drop_counts = await read_drag_probe_counts(to_locator)
                    drop_observed = drag_probe_drop_count(drop_counts) > 0
        finally:
            await cleanup_drag_probe(to_locator)
        if source_html5_draggable and not drop_observed:
            raise MCPToolError(
                -32603,
                "browser_drag completed but no HTML5 drop event was observed on the page.",
                data={
                    "drop_observed": False,
                    "fallback_used": fallback_used,
                    "event_counts": drop_counts,
                },
            )
        await finalize_locked_browser_action(
            utility_tools,
            state,
            tool_name="browser_drag",
            persist_reason="browser_drag",
        )
        return {
            "dragged": True,
            "drop_observed": drop_observed,
            "fallback_used": fallback_used,
        }
