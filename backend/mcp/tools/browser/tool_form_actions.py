"""SoAI - Browser tools: form actions [backend/mcp/tools/browser/tool_form_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import Error

from mcp.tools.argument_fields import (
    optional_non_empty_string,
    require_allowed_keys,
    require_non_empty_string,
)
from mcp.tools.argument_scalars import parse_bool_strict_default
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
)
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.openai_owner_context import has_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "tool_browser_press_key",
    "tool_browser_type",
)


def _build_sensitive_field_message(owner_key: str) -> str:
    if has_openai_conversation_owner(owner_key):
        return (
            "browser_type is not allowed on sensitive fields (password/OTP). "
            "Use browser_autofill_secret or browser_autofill_vault instead."
        )
    return (
        "browser_type is not allowed on sensitive fields (password/OTP). "
        "Use browser_autofill_vault instead."
    )


async def tool_browser_type(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "element",
                "ref",
                "text",
                "submit",
                "include_snapshot",
                "snapshot_roles",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_type",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    ref = require_ref(arguments)
    include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
    text_raw = get_arg(arguments, "text")
    if not isinstance(text_raw, str):
        raise MCPToolError(-32602, "Parameter 'text' must be a string")
    submit = parse_bool_strict_default(arguments.get("submit"), field_name="submit", default=False)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(utility_tools, state)
            page = preflight.page
            stabilize_ms = preflight.stabilize_ms
            raise_if_dialog_pending(state, tool_name="browser_type")
            role, _name, _nth, _frame_path = resolve_ref_mapping(state, page, ref)
            if role not in {"textbox", "searchbox", "combobox"}:
                raise MCPToolError(
                    -32602,
                    f"browser_type requires a typeable element role (textbox/searchbox/combobox); ref '{ref}' resolved to role '{role}'",
                )
            locator = locator_by_ref(state, page, ref)
        try:
            async with action_timeout_scope(utility_tools, stabilize_ms=stabilize_ms):
                type_attr_raw = await locator.get_attribute("type")
                type_attr = type_attr_raw.strip().lower() if isinstance(type_attr_raw, str) else ""
                autocomplete_raw = await locator.get_attribute("autocomplete")
                autocomplete = (
                    autocomplete_raw.strip().lower() if isinstance(autocomplete_raw, str) else ""
                )
                inputmode_raw = await locator.get_attribute("inputmode")
                inputmode = inputmode_raw.strip().lower() if isinstance(inputmode_raw, str) else ""
                tag_name_raw = await locator.evaluate("element => element.tagName.toLowerCase()")
                tag_name = tag_name_raw.strip().lower() if isinstance(tag_name_raw, str) else ""
                if type_attr == "password" or autocomplete in {
                    "current-password",
                    "new-password",
                    "one-time-code",
                }:
                    raise MCPToolError(
                        -32602,
                        _build_sensitive_field_message(owner_key),
                    )
                if inputmode in {"numeric", "tel"} and autocomplete == "one-time-code":
                    raise MCPToolError(
                        -32602,
                        _build_sensitive_field_message(owner_key),
                    )
                if tag_name == "select":
                    raise MCPToolError(
                        -32602,
                        "browser_type cannot be used on native select controls. Use browser_select_option instead.",
                    )
                await locator.fill(text_raw)
                if submit:
                    await locator.press("Enter")
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
        except (TimeoutError, Error) as exception:
            raise_rewritten_interaction_exception(exception, tool_name="browser_type")
        async with state.lock:
            return await build_action_success_payload(
                utility_tools,
                state,
                preflight=preflight,
                reason="browser_type",
                snapshot=BrowserInlineSnapshotRequest(include_snapshot, snapshot_roles),
                success=BrowserActionSuccessFlag("typed", True),
            )


async def tool_browser_press_key(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {"key", "include_snapshot", "snapshot_roles", *BROWSER_SESSION_PARAM_KEYS},
        ),
        tool_name="browser_press_key",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    key = require_non_empty_string(get_arg(arguments, "key"), key="key")
    include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(utility_tools, state)
            page = preflight.page
            stabilize_ms = preflight.stabilize_ms
            raise_if_dialog_pending(state, tool_name="browser_press_key")
        try:
            async with action_timeout_scope(utility_tools, stabilize_ms=stabilize_ms):
                await page.keyboard.press(key)
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
        except (TimeoutError, Error) as exception:
            raise_rewritten_interaction_exception(exception, tool_name="browser_press_key")
        async with state.lock:
            return await build_action_success_payload(
                utility_tools,
                state,
                preflight=preflight,
                reason="browser_press_key",
                snapshot=BrowserInlineSnapshotRequest(include_snapshot, snapshot_roles),
                success=BrowserActionSuccessFlag("pressed", True),
            )
