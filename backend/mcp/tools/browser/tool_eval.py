"""SoAI - Browser tool: browser_eval [backend/mcp/tools/browser/tool_eval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.mcp.argument_shapes import require_trimmed_bounded_string_value
from core.validation.integers import is_strict_int
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.browser.action_preflight import prepare_action_page_preflight
from mcp.tools.browser.download_support import downloads_to_dicts
from mcp.tools.browser.interaction_failures import (
    raise_if_dialog_pending,
    rewrite_interaction_exception,
)
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.storage_state import (
    persist_synced_browser_action_storage_state,
    sync_browser_action_state,
)
from mcp.tools.browser.timeouts import build_wall_clock_timeout_sec
from mcp.tools.error import MCPToolError, build_invalid_params_error, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_eval",)


def _require_js_eval_enabled(utility_tools: MCPUtilityToolsProtocol) -> None:
    if not utility_tools.config.get_bool("TOOLS.MCP.BROWSER.JS_EVAL_ENABLED"):
        raise MCPToolError(
            -32603,
            "browser_eval is disabled by configuration (TOOLS.MCP.BROWSER.JS_EVAL_ENABLED=false).",
        )


def _resolve_max_script_chars(utility_tools: MCPUtilityToolsProtocol) -> int:
    raw = utility_tools.config.get_int("TOOLS.MCP.BROWSER.JS_EVAL_MAX_SCRIPT_CHARS")
    if not is_strict_int(raw):
        return 10000
    return max(256, min(100000, int(raw)))


def _resolve_default_timeout_ms(utility_tools: MCPUtilityToolsProtocol) -> int:
    raw = utility_tools.config.get_int("TOOLS.MCP.BROWSER.JS_EVAL_TIMEOUT_MS")
    if not is_strict_int(raw):
        return 15000
    return max(1000, min(300000, int(raw)))


def _resolve_timeout_ms(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> int:
    default = _resolve_default_timeout_ms(utility_tools)
    value = arguments.get("timeout_ms")
    if value is None:
        return default
    parsed = parse_optional_int_strict(
        value,
        field_name="timeout_ms",
        min_value=1000,
        max_value=300000,
    )
    return default if parsed is None else int(parsed)


def _require_script(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> str:
    raw = get_arg(arguments, "script")
    max_chars = _resolve_max_script_chars(utility_tools)
    return require_trimmed_bounded_string_value(
        raw,
        build_error=build_invalid_params_error,
        type_message="Parameter 'script' must be a non-empty string",
        empty_message="Parameter 'script' must be a non-empty string",
        max_length_message=f"script exceeds max length ({max_chars} characters)",
        max_length=max_chars,
    )


def _resolve_arg(arguments: JSONDict) -> JSONValue:
    return arguments.get("arg")


def _wrap_as_function_body(script: str) -> str:
    return f"(async function(arg) {{ {script} }})"


def _resolve_result_type(value: JSONValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


async def tool_browser_eval(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"script", "arg", "timeout_ms", *BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_eval",
    )
    _require_js_eval_enabled(utility_tools)
    _store, state = await require_existing_session(utility_tools, arguments)
    script = _require_script(utility_tools, arguments)
    arg = _resolve_arg(arguments)
    timeout_ms = _resolve_timeout_ms(utility_tools, arguments)
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(utility_tools, state)
            downloads_dir = preflight.downloads_dir
            page = preflight.page
            raise_if_dialog_pending(state, tool_name="browser_eval")

        raw_result: JSONValue
        try:
            async with asyncio.timeout(
                build_wall_clock_timeout_sec(
                    timeout_ms=timeout_ms,
                    fallback_timeout_sec=float(timeout_ms) / 1000.0,
                    extra_wait_ms=0,
                    buffer_sec=10.0,
                ),
            ):
                await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                raw_result = await page.evaluate(_wrap_as_function_body(script), arg)
        except (TimeoutError, Error) as exception:
            rewritten = rewrite_interaction_exception(exception, tool_name="browser_eval")
            if rewritten is not None:
                raise rewritten from exception
            if isinstance(exception, Error) and not str(exception).strip():
                raise MCPToolError(
                    -32603,
                    "browser_eval failed with an empty Playwright error. A blocking dialog or a destroyed execution context is likely; call browser_dialog(action='list') and retry.",
                ) from exception
            raise

        async with state.lock:
            await sync_browser_action_state(
                utility_tools=utility_tools,
                state=state,
                downloads_dir=downloads_dir,
            )
            await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_eval",
            )
            await persist_synced_browser_action_storage_state(
                utility_tools=utility_tools,
                state=state,
                reason="browser_eval",
            )
            result: JSONValue = raw_result
            return {
                "evaluated": True,
                "result": result,
                "result_type": _resolve_result_type(result),
                "downloads_dir": downloads_dir,
                "downloads": downloads_to_dicts(state.downloads),
            }
