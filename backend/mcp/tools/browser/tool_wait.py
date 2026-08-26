"""SoAI - Browser tool: browser_wait_for [backend/mcp/tools/browser/tool_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

from mcp.tools.argument_fields import (
    optional_non_empty_string,
    require_allowed_keys,
)
from mcp.tools.argument_scalars import (
    parse_optional_int_strict,
    parse_optional_number_strict,
)
from mcp.tools.browser.argument_validation import (
    parse_optional_wait_until_strict,
)
from mcp.tools.browser.interaction_failures import rewrite_interaction_exception
from mcp.tools.browser.ref_lookup import locator_and_role_by_ref, optional_ref
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.text_visibility_wait import (
    wait_for_any_text_visible,
    wait_for_text_hidden,
)
from mcp.tools.browser.timeouts import (
    build_wall_clock_timeout_sec,
    resolve_action_timeout_sec,
    resolve_max_wait_sec,
)
from mcp.tools.browser.url_wait_patterns import (
    build_url_prefix_wait_pattern,
    build_url_wait_pattern,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from re import Pattern
    from typing import Literal

    from core.types.json import JSONDict
    from mcp.tools.browser.argument_validation import PageWaitUntil
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_wait_for",)


async def tool_browser_wait_for(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "time",
                "text",
                "text_gone",
                "url_pattern",
                "url_prefix",
                "wait_until",
                "timeout_ms",
                "ref",
                "state",
                "reason",
            },
        )
        | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_wait_for",
    )
    _ = optional_non_empty_string(arguments.get("reason"), key="reason")
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    async with browser_action_lock(state):
        time_value = parse_optional_number_strict(
            arguments.get("time"),
            field_name="time",
            min_value=0.0,
            max_value=3600.0,
        )
        text_value = optional_non_empty_string(arguments.get("text"), key="text")
        text_gone_value = optional_non_empty_string(
            arguments.get("text_gone"),
            key="text_gone",
        )
        url_pattern_raw = optional_non_empty_string(
            arguments.get("url_pattern"),
            key="url_pattern",
        )
        url_prefix_raw = optional_non_empty_string(
            arguments.get("url_prefix"),
            key="url_prefix",
        )
        url_wait_until_raw = parse_optional_wait_until_strict(
            arguments.get("wait_until"),
            field_name="wait_until",
        )
        timeout_ms = parse_optional_int_strict(
            arguments.get("timeout_ms"),
            field_name="timeout_ms",
            min_value=1,
            max_value=300_000,
        )
        ref = optional_ref(arguments)
        if ref is not None:
            normalized = str(ref).strip().lower()
            if normalized.startswith(":") and ("text(" in normalized or "has-text(" in normalized):
                raise MCPToolError(
                    -32602,
                    (
                        "ref must be a browser_snapshot ref (e.g. e7) or a snapshot alias. "
                        "Use text/textGone to wait for text, or call browser_snapshot and use the returned ref."
                    ),
                )
        state_value_raw = arguments.get("state")
        wait_state: Literal["visible", "hidden", "attached", "detached"] = "visible"
        if state_value_raw is not None:
            if ref is None:
                raise MCPToolError(-32602, "state is only allowed when ref is provided")
            if not isinstance(state_value_raw, str) or not state_value_raw.strip():
                raise MCPToolError(-32602, "state must be a non-empty string when provided")
            normalized_state = state_value_raw.strip().lower()
            if normalized_state == "visible":
                wait_state = "visible"
            elif normalized_state == "hidden":
                wait_state = "hidden"
            elif normalized_state == "attached":
                wait_state = "attached"
            elif normalized_state == "detached":
                wait_state = "detached"
            else:
                raise MCPToolError(
                    -32602,
                    "state must be one of: visible, hidden, attached, detached",
                )
        has_text = text_value is not None
        has_text_gone = text_gone_value is not None
        has_url_pattern = url_pattern_raw is not None
        has_url_prefix = url_prefix_raw is not None
        if has_url_pattern and has_url_prefix:
            raise MCPToolError(-32602, "url_pattern and url_prefix are mutually exclusive")
        if url_wait_until_raw is not None and not (has_url_pattern or has_url_prefix):
            raise MCPToolError(
                -32602,
                "wait_until is only allowed when url_pattern or url_prefix is provided",
            )
        url_wait_until: PageWaitUntil | None = url_wait_until_raw
        if (has_url_pattern or has_url_prefix) and url_wait_until is None:
            url_wait_until = "domcontentloaded"
        url_pattern: Pattern[str] | None = None
        if has_url_pattern and url_pattern_raw is not None:
            url_pattern = build_url_wait_pattern(url_pattern_raw)
        if has_url_prefix and url_prefix_raw is not None:
            url_pattern = build_url_prefix_wait_pattern(url_prefix_raw)
        has_any = any(
            (
                time_value is not None,
                has_text,
                has_text_gone,
                has_url_pattern,
                has_url_prefix,
                ref is not None,
            ),
        )
        if not has_any:
            raise MCPToolError(
                -32602,
                "browser_wait_for requires one of: time, text, text_gone, url_pattern, url_prefix, ref",
            )
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page = require_current_page(state)
            await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_wait_for",
            )
            locator = None
            ref_role = None
            if ref is not None:
                ref_role, locator = locator_and_role_by_ref(state, page, ref)
                if state_value_raw is None and ref_role == "option":
                    wait_state = "attached"
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
            max_wait_sec = resolve_max_wait_sec(utility_tools)
            wait_timeout_ms = (
                timeout_ms if timeout_ms is not None else int(action_timeout_sec) * 1000
            )
            wall_clock_timeout_sec = build_wall_clock_timeout_sec(
                timeout_ms=wait_timeout_ms,
                fallback_timeout_sec=float(action_timeout_sec),
                extra_wait_ms=0,
                buffer_sec=10.0,
            )
            seconds = 0.0 if time_value is None else float(time_value)
            if time_value is not None and seconds > max_wait_sec:
                raise MCPToolError(
                    -32602,
                    f"time must be <= {max_wait_sec:.0f} seconds (config: TOOLS.MCP.BROWSER.MAX_WAIT_SEC)",
                )
            if time_value is not None:
                wall_clock_timeout_sec = max(wall_clock_timeout_sec, 1.0, seconds + 5.0)
        try:
            async with asyncio.timeout(wall_clock_timeout_sec):
                if time_value is not None:
                    await page.wait_for_timeout(int(seconds * 1000))
                if has_text:
                    _ = await wait_for_any_text_visible(
                        page,
                        text=str(text_value),
                        timeout_ms=wait_timeout_ms,
                    )
                if has_text_gone:
                    _ = await wait_for_text_hidden(
                        page,
                        text=str(text_gone_value),
                        timeout_ms=wait_timeout_ms,
                    )
                if url_pattern is not None:
                    await page.wait_for_url(
                        url_pattern,
                        timeout=wait_timeout_ms,
                        wait_until=url_wait_until,
                    )
                if locator is not None:
                    await locator.wait_for(state=wait_state, timeout=wait_timeout_ms)
        except (TimeoutError, Error) as exception:
            rewritten = rewrite_interaction_exception(exception, tool_name="browser_wait_for")
            if rewritten is not None:
                raise rewritten from exception
            raise
        output_url = await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_wait_for",
        )
        return {"waited": True, "url": output_url}
