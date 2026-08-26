"""SoAI - Browser tools: navigation [backend/mcp/tools/browser/tool_navigation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from playwright.async_api import HttpCredentials

from core.errors.cancellation import raise_cancelled_error
from mcp.tools.argument_fields import (
    require_allowed_keys,
    require_non_empty_string,
)
from mcp.tools.argument_scalars import (
    parse_bool_strict_default,
    parse_optional_bool_strict,
)
from mcp.tools.browser.argument_validation import (
    parse_inline_snapshot_request,
)
from mcp.tools.browser.config_values import (
    resolve_browser_default_nav_timeout_sec,
    resolve_browser_render_stabilize_ms,
)
from mcp.tools.browser.download_flow_hints import build_download_flow_hints
from mcp.tools.browser.http_auth_support import (
    build_playwright_http_credentials,
    parse_http_auth_block,
    resolve_http_auth_credentials,
)
from mcp.tools.browser.navigation_arguments import (
    resolve_navigate_wait_until,
    resolve_navigation_tab_id,
    resolve_navigation_timeout_ms,
)
from mcp.tools.browser.navigation_errors import raise_navigation_playwright_tool_error
from mcp.tools.browser.navigation_result_assembly import (
    NavigationResultPlan,
    build_captured_navigation_result,
)
from mcp.tools.browser.navigation_validation import build_navigation_url_candidates
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.playwright_tool_errors import raise_playwright_tool_error
from mcp.tools.browser.security_policy import enforce_browser_navigation_policy
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    mark_page_load,
    require_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.timeouts import build_wall_clock_timeout_sec
from mcp.tools.browser.tool_navigation_attempt import (
    perform_navigation_with_http_fallback,
)
from mcp.tools.browser.tool_navigation_history import (
    execute_browser_history_navigation,
)
from mcp.tools.browser.tool_navigation_runtime import (
    read_navigation_page,
    run_post_navigation,
)
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_navigate",)

OPERATION_MCP_BROWSER_NAVIGATE_CAPTURE_SCREENSHOT = "mcp_browser.tool_navigation.capture_screenshot"
NAVIGATE_SCREENSHOT_FAILURE_MESSAGE = "Browser navigation screenshot capture failed."
URL_NAVIGATION_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {
        "url",
        "tab_id",
        "wait_until",
        "timeout_ms",
        "accept_insecure",
        "http_auth",
        "clear_http_auth",
    },
)


async def tool_browser_navigate(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=URL_NAVIGATION_ARGUMENT_KEYS
        | frozenset({"action", "include_snapshot", "snapshot_roles", *BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_navigate",
    )
    action = require_non_empty_string(get_arg(arguments, "action"), key="action").lower()
    if action not in {"url", "back", "forward"}:
        raise MCPToolError(-32602, "action must be one of: url, back, forward")
    if action != "url":
        invalid_fields = sorted(
            field_name for field_name in URL_NAVIGATION_ARGUMENT_KEYS if field_name in arguments
        )
        if invalid_fields:
            joined_fields = ", ".join(invalid_fields)
            raise MCPToolError(
                -32602,
                f"{joined_fields} are not allowed for action={action}",
            )
        return await execute_browser_history_navigation(
            utility_tools,
            arguments,
            navigate_backwards=action == "back",
        )
    url = require_non_empty_string(get_arg(arguments, "url"), key="url")
    tab_id_value = resolve_navigation_tab_id(arguments)
    primary_url, fallback_url = build_navigation_url_candidates(url)
    http_auth = parse_http_auth_block(arguments.get("http_auth"))
    clear_http_auth = parse_bool_strict_default(
        arguments.get("clear_http_auth"),
        field_name="clear_http_auth",
        default=False,
    )
    accept_insecure = parse_optional_bool_strict(
        arguments.get("accept_insecure"),
        field_name="accept_insecure",
    )
    normalized_scheme = (urlparse(primary_url).scheme or "").lower()
    is_network_url = normalized_scheme in {"http", "https"}
    is_non_network_url = not is_network_url
    if is_non_network_url and http_auth is not None:
        raise MCPToolError(-32602, "http_auth is only supported for http(s) URLs.")
    if is_non_network_url and clear_http_auth:
        raise MCPToolError(
            -32602,
            "clear_http_auth is only supported for http(s) URLs.",
        )
    if is_non_network_url and accept_insecure is not None:
        raise MCPToolError(
            -32602,
            "accept_insecure is only supported for http(s) URLs.",
        )
    if clear_http_auth and http_auth is not None:
        raise MCPToolError(-32602, "http_auth and clear_http_auth cannot be used together.")
    await enforce_browser_navigation_policy(
        utility_tools.config,
        utility_tools.runtime_flags,
        url=primary_url,
        source="MCP browser navigation",
    )
    store, state = await require_session(utility_tools, arguments)
    async with browser_action_lock(state):
        include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
        keep_http_credentials = http_auth is None and not clear_http_auth
        requested_http_credentials: HttpCredentials | None = None
        if http_auth is not None:
            if not is_network_url:
                raise MCPToolError(-32602, "http_auth is only supported for http(s) URLs.")
            url_candidates: list[str] = [primary_url]
            if fallback_url is not None:
                url_candidates.append(fallback_url)
            username, password = await resolve_http_auth_credentials(
                utility_tools,
                http_auth=http_auth,
                url_candidates=tuple(url_candidates),
                tool_name="browser_navigate",
            )
            requested_http_credentials = build_playwright_http_credentials(username, password)
            keep_http_credentials = False
        if clear_http_auth:
            keep_http_credentials = False
            requested_http_credentials = None

        needs_context_recreate = (not keep_http_credentials) or (accept_insecure is not None)
        if needs_context_recreate:
            if not is_network_url:
                raise MCPToolError(
                    -32602,
                    "accept_insecure/http_auth are only supported for http(s) URLs.",
                )
            should_recreate_context = False
            desired_http_credentials: HttpCredentials | None = None
            desired_ignore_https_errors = False
            async with state.lock:
                await sync_session_state(utility_tools.config, state)
                desired_http_credentials = (
                    state.http_credentials if keep_http_credentials else requested_http_credentials
                )
                desired_ignore_https_errors = (
                    state.ignore_https_errors if accept_insecure is None else bool(accept_insecure)
                )
                should_recreate_context = (
                    desired_http_credentials != state.http_credentials
                    or bool(desired_ignore_https_errors) != bool(state.ignore_https_errors)
                )
            if should_recreate_context:
                await store.recreate_context(
                    state=state,
                    http_credentials=desired_http_credentials,
                    ignore_https_errors=bool(desired_ignore_https_errors),
                )
        async with state.lock:
            downloads_dir, page = await read_navigation_page(
                utility_tools,
                state,
                desired_tab_id=tab_id_value,
            )
            if tab_id_value is not None:
                try:
                    await page.bring_to_front()
                except asyncio.CancelledError as exception:
                    raise_cancelled_error(exception)
                except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                    raise_playwright_tool_error(state, exception=exception)
            wait_until = resolve_navigate_wait_until(arguments)
            timeout_ms = resolve_navigation_timeout_ms(arguments)
            nav_timeout_sec = resolve_browser_default_nav_timeout_sec(utility_tools.config)
            stabilize_ms = resolve_browser_render_stabilize_ms(utility_tools.config)
            wall_clock_timeout_sec = build_wall_clock_timeout_sec(
                timeout_ms=timeout_ms,
                fallback_timeout_sec=float(nav_timeout_sec),
                extra_wait_ms=0,
                buffer_sec=10.0,
            )
            mark_page_load(state)
        try:
            async with asyncio.timeout(wall_clock_timeout_sec):
                download_started = await perform_navigation_with_http_fallback(
                    utility_tools=utility_tools,
                    state=state,
                    page=page,
                    primary_url=primary_url,
                    fallback_url=fallback_url,
                    wait_until=wait_until,
                    timeout_ms=timeout_ms,
                )
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
            raise_navigation_playwright_tool_error(
                state,
                exception=exception,
                attempted_url=primary_url,
            )

        download_result_fields: JSONDict = {}
        download_skip_reason: str | None = None
        if download_started:
            download_skip_reason = (
                "Navigation initiated a download; the page did not navigate. "
                f"Use read_document(url={url!r}) to read the downloaded document, "
                "or browser_downloads to inspect saved browser downloads."
            )
            download_result_fields["download_started"] = True
            download_result_fields.update(
                build_download_flow_hints(
                    url=url,
                    profile=state.profile,
                    session_scope=state.session_scope,
                    include_navigate=False,
                ),
            )
        url_result_plan = NavigationResultPlan(
            title_timeout_ms=(
                timeout_ms if timeout_ms is not None else int(nav_timeout_sec) * 1000
            ),
            include_snapshot=include_snapshot,
            snapshot_roles=snapshot_roles,
            screenshot_operation=OPERATION_MCP_BROWSER_NAVIGATE_CAPTURE_SCREENSHOT,
            screenshot_failure_message=NAVIGATE_SCREENSHOT_FAILURE_MESSAGE,
            screenshot_skip_reason=download_skip_reason,
            extra_fields=download_result_fields,
        )

        async def build_locked_result(page_after_navigation: Page) -> JSONDict:
            return await build_captured_navigation_result(
                utility_tools,
                state,
                page_after_navigation,
                url_result_plan,
            )

        navigation_result = await run_post_navigation(
            utility_tools=utility_tools,
            state=state,
            page=page,
            on_locked_page=build_locked_result,
            downloads_dir=downloads_dir,
            stabilize_ms=stabilize_ms,
            tool_name="browser_navigate",
        )
        return navigation_result
