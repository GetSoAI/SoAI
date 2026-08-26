"""SoAI - Browser tool: browser_dialog [backend/mcp/tools/browser/tool_dialog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from core.mcp.argument_shapes import require_trimmed_bounded_string_value
from core.mcp.argument_validation import require_non_empty_string_value
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_state import (
    mark_browser_session_from_playwright_exception,
)
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.error import MCPToolError, build_invalid_params_error, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_dialog",)


def _require_action(arguments: JSONDict) -> str:
    raw = get_arg(arguments, "action")
    return require_non_empty_string_value(
        raw,
        build_error=build_invalid_params_error,
        type_message="action must be a non-empty string",
        empty_message="action must be a non-empty string",
    ).lower()


def _optional_dialog_id(arguments: JSONDict) -> str | None:
    value = arguments.get("dialog_id")
    if value is None:
        return None
    return require_non_empty_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message="dialog_id must be a non-empty string when provided",
        empty_message="dialog_id must be a non-empty string when provided",
    )


def _resolve_prompt_text(arguments: JSONDict) -> str | None:
    value = arguments.get("prompt_text")
    if value is None:
        return None
    return require_trimmed_bounded_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message="prompt_text must be a string when provided",
        empty_message="prompt_text must be a non-empty string when provided",
        max_length_message="prompt_text is too long",
        max_length=5000,
    )


def _clear_dialog_state(state: BrowserSessionState, dialog_id: str) -> None:
    state.dialog_objects.pop(dialog_id, None)
    state.dialogs = [item for item in state.dialogs if item.dialog_id != dialog_id]


def _rewrite_dialog_failure(
    *,
    action: str,
    dialog_id: str,
    exception: BaseException,
) -> MCPToolError:
    if isinstance(exception, TimeoutError):
        return MCPToolError(
            -32603,
            f"browser_dialog timed out while trying to {action} dialog '{dialog_id}'.",
        )
    message = str(exception).strip()
    if not message:
        message = "unknown Playwright error"
    return MCPToolError(
        -32603,
        f"browser_dialog failed while trying to {action} dialog '{dialog_id}': {message}",
    )


async def tool_browser_dialog(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"action", "dialog_id", "prompt_text"}) | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_dialog",
    )
    action = _require_action(arguments)
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    async with browser_action_lock(state):
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            if action == "list":
                return {
                    "dialogs": [
                        {
                            "dialog_id": item.dialog_id,
                            "type": item.type,
                            "message": item.message,
                            "default_value": item.default_value,
                        }
                        for item in list(state.dialogs)
                    ],
                }
            if action in {"accept", "dismiss", "prompt"}:
                dialog_id = _optional_dialog_id(arguments)
                if dialog_id is None:
                    pending = list(state.dialogs)
                    if not pending:
                        raise MCPToolError(
                            -32602,
                            "No pending dialogs to handle. Call browser_dialog(action='list') to confirm.",
                        )
                    if len(pending) != 1:
                        ids = [
                            str(item.dialog_id)
                            for item in pending
                            if str(item.dialog_id or "").strip()
                        ]
                        raise MCPToolError(
                            -32602,
                            "dialog_id is required when multiple dialogs are pending. Call browser_dialog(action='list') to get dialog_id values.",
                            {"dialog_ids": ids},
                        )
                    dialog_id = str(pending[0].dialog_id)
                dialog = state.dialog_objects.get(dialog_id)
                if dialog is None:
                    raise MCPToolError(-32602, f"Unknown dialog_id: {dialog_id}")
                prompt_text = _resolve_prompt_text(arguments)
                if action == "prompt" and prompt_text is None:
                    raise MCPToolError(-32602, "prompt_text is required for action=prompt")
                try:
                    async with asyncio.timeout(INTERACTIVE_TIMEOUT_SEC):
                        if action == "dismiss":
                            await dialog.dismiss()
                        elif prompt_text is None:
                            await dialog.accept()
                        else:
                            await dialog.accept(prompt_text=prompt_text)
                except TimeoutError as exception:
                    raise _rewrite_dialog_failure(
                        action=action,
                        dialog_id=dialog_id,
                        exception=exception,
                    ) from exception
                except asyncio.CancelledError as exception:
                    raise_cancelled_error(exception)
                except PLAYWRIGHT_OPERATION_EXCEPTIONS as playwright_error:
                    mark_browser_session_from_playwright_exception(
                        state,
                        exception=playwright_error,
                    )
                    if state.context_closed:
                        _clear_dialog_state(state, dialog_id)
                    raise _rewrite_dialog_failure(
                        action=action,
                        dialog_id=dialog_id,
                        exception=playwright_error,
                    ) from playwright_error
                _clear_dialog_state(state, dialog_id)
                return {"handled": True, "action": action, "dialog_id": dialog_id}
            raise MCPToolError(-32602, "Invalid action. Expected: list|accept|dismiss|prompt")
