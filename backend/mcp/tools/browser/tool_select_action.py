"""SoAI - Browser tools: select action [backend/mcp/tools/browser/tool_select_action.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import Error

from mcp.tools.argument_fields import optional_non_empty_string, require_allowed_keys
from mcp.tools.browser.action_preflight import prepare_action_page_preflight
from mcp.tools.browser.action_result_payloads import (
    BrowserActionSuccessFlag,
    BrowserInlineSnapshotRequest,
    build_action_success_payload,
)
from mcp.tools.browser.argument_validation import (
    parse_inline_snapshot_request,
)
from mcp.tools.browser.interaction_failures import (
    raise_if_dialog_pending,
    raise_rewritten_interaction_exception,
)
from mcp.tools.browser.ref_lookup import (
    locator_by_ref,
    require_ref,
    resolve_ref_mapping,
)
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.timeouts import (
    action_timeout_scope,
    resolve_action_timeout_sec,
)
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_select_option",)


async def tool_browser_select_option(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "element",
                "ref",
                "values",
                "include_snapshot",
                "snapshot_roles",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_select_option",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    ref = require_ref(arguments)
    include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
    values_raw = get_arg(arguments, "values")
    if (
        not isinstance(values_raw, list)
        or not values_raw
        or not all(isinstance(value, str) and value for value in values_raw)
    ):
        raise MCPToolError(-32602, "Parameter 'values' must be a non-empty string array")
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(utility_tools, state)
            page = preflight.page
            stabilize_ms = preflight.stabilize_ms
            raise_if_dialog_pending(state, tool_name="browser_select_option")
            role, _name, _nth, _frame_path = resolve_ref_mapping(state, page, ref)
            if role != "combobox":
                raise MCPToolError(
                    -32602,
                    (
                        "browser_select_option requires a select/combobox ref from browser_snapshot; "
                        f"ref '{ref}' resolved to role '{role}'."
                    ),
                )
            locator = locator_by_ref(state, page, ref)
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
        try:
            async with action_timeout_scope(utility_tools, stabilize_ms=stabilize_ms):
                tag_name_raw = await locator.evaluate("element => element.tagName.toLowerCase()")
                tag_name = tag_name_raw.strip().lower() if isinstance(tag_name_raw, str) else ""
                if tag_name != "select":
                    raise MCPToolError(
                        -32602,
                        "browser_select_option only supports native <select> controls. Use browser_click or browser_type for custom combobox widgets.",
                    )
                await locator.select_option(
                    label=[str(label) for label in values_raw],
                    timeout=int(action_timeout_sec) * 1000,
                )
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
        except (TimeoutError, Error) as exception:
            raise_rewritten_interaction_exception(exception, tool_name="browser_select_option")
        async with state.lock:
            return await build_action_success_payload(
                utility_tools,
                state,
                preflight=preflight,
                reason="browser_select_option",
                snapshot=BrowserInlineSnapshotRequest(include_snapshot, snapshot_roles),
                success=BrowserActionSuccessFlag("selected", True),
            )
