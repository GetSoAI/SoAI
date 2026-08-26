"""SoAI - Browser tools: logs [backend/mcp/tools/browser/tool_logs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import (
    parse_bool_strict_default,
    parse_optional_int_strict,
)
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.browser.types import BrowserConsoleMessage, BrowserNetworkRequest
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "tool_browser_console",
    "tool_browser_network",
)


def _since_label(value: JSONValue) -> str:
    if value is None:
        return "last_call"
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32602, "since must be a non-empty string when provided")
    return value.strip().lower()


def _dedupe_console_messages(messages: list[BrowserConsoleMessage]) -> list[JSONDict]:
    output: list[JSONDict] = []
    counts: dict[tuple[str, str, str | None, int | None, int | None], int] = {}
    order: list[tuple[str, str, str | None, int | None, int | None]] = []
    for msg in messages:
        key = (msg.type, msg.text, msg.url, msg.line, msg.column)
        existing = counts.get(key)
        if existing is None:
            counts[key] = 1
            order.append(key)
            continue
        counts[key] = existing + 1
    for key in order:
        msg_type, text, url, line, column = key
        item: JSONDict = {"type": msg_type, "text": text}
        if url is not None:
            item["url"] = url
        if line is not None:
            item["line"] = line
        if column is not None:
            item["column"] = column
        count = counts.get(key, 1)
        if count != 1:
            item["count"] = int(count)
        output.append(item)
    return output


def _requests_to_dicts(
    requests: list[BrowserNetworkRequest],
    *,
    include_body: bool,
) -> list[JSONDict]:
    output: list[JSONDict] = []
    for req in requests:
        item: JSONDict = {
            "url": req.url,
            "method": req.method,
            "resource_type": str(req.resource_type or ""),
        }
        if req.status is not None:
            item["status"] = req.status
        if isinstance(req.failure_text, str) and req.failure_text:
            item["failure_text"] = req.failure_text
        if include_body and isinstance(req.body, str) and req.body:
            item["body"] = req.body
            if isinstance(req.body_truncated, bool):
                item["body_truncated"] = req.body_truncated
        output.append(item)
    return output


async def tool_browser_console(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"since", "type_filter", *BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_console",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    since = _since_label(arguments.get("since"))
    filter_raw = arguments.get("type_filter")
    type_filter = "all"
    if filter_raw is not None:
        if not isinstance(filter_raw, str) or not filter_raw.strip():
            raise MCPToolError(-32602, "type_filter must be a non-empty string when provided")
        normalized_filter = filter_raw.strip().lower()
        if normalized_filter not in {"all", "errors", "warnings", "errors_warnings"}:
            raise MCPToolError(
                -32602,
                "type_filter must be one of: all, errors, warnings, errors_warnings",
            )
        type_filter = normalized_filter
    if since not in {"last_call", "page_load"}:
        raise MCPToolError(-32602, "since must be one of: last_call, page_load")
    async with state.lock:
        await sync_session_state(utility_tools.config, state)
        page = require_current_page(state)
        await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_console",
        )
        start = (
            state.console_last_call_index if since == "last_call" else state.console_page_load_index
        )
        items = state.console_messages
        drained_messages = items[max(0, start) :]
        state.console_last_call_index = len(items)
        if type_filter == "all":
            return {"messages": _dedupe_console_messages(drained_messages)}
        allowed_types: set[str]
        if type_filter == "errors":
            allowed_types = {"error"}
        elif type_filter == "warnings":
            allowed_types = {"warning"}
        else:
            allowed_types = {"error", "warning"}
        filtered = [
            message
            for message in drained_messages
            if str(message.type or "").strip().lower() in allowed_types
        ]
        return {"messages": _dedupe_console_messages(filtered)}


async def tool_browser_network(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "since",
                "cursor",
                "resource_type",
                "status_gte",
                "include_body",
                "max_requests",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_network",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    cursor_value = parse_optional_int_strict(
        arguments.get("cursor"),
        field_name="cursor",
        min_value=0,
        max_value=10_000_000,
    )
    if cursor_value is not None and arguments.get("since") is not None:
        raise MCPToolError(-32602, "since is not allowed when cursor is provided")
    since = _since_label(arguments.get("since"))
    include_body = parse_bool_strict_default(
        arguments.get("include_body"),
        field_name="include_body",
        default=False,
    )
    max_requests_value = parse_optional_int_strict(
        arguments.get("max_requests"),
        field_name="max_requests",
        min_value=1,
        max_value=500,
    )
    max_requests = int(max_requests_value) if max_requests_value is not None else 200
    resource_type_raw = arguments.get("resource_type")
    status_gte = parse_optional_int_strict(
        arguments.get("status_gte"),
        field_name="status_gte",
        min_value=0,
        max_value=999,
    )
    resource_type: str | None = None
    if resource_type_raw is not None:
        if not isinstance(resource_type_raw, str) or not resource_type_raw.strip():
            raise MCPToolError(-32602, "resource_type must be a non-empty string when provided")
        resource_type = resource_type_raw.strip().lower()
    if since not in {"last_call", "page_load"}:
        raise MCPToolError(-32602, "since must be one of: last_call, page_load")
    async with state.lock:
        await sync_session_state(utility_tools.config, state)
        page = require_current_page(state)
        await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_network",
        )
        if cursor_value is not None:
            start = int(cursor_value)
        else:
            start = (
                state.network_last_call_index
                if since == "last_call"
                else state.network_page_load_index
            )
        items = state.network_requests
        total_captured = len(items)
        if start < 0 or start > total_captured:
            raise MCPToolError(
                -32602,
                f"cursor must be <= {total_captured}",
                data={"total_captured": int(total_captured)},
            )
        filtered_requests: list[BrowserNetworkRequest] = []
        processed_count = 0
        index = int(start)
        while index < total_captured:
            req = items[index]
            index += 1
            processed_count += 1
            if resource_type is not None:
                if str(req.resource_type or "").strip().lower() != resource_type:
                    continue
            if status_gte is not None and req.status is not None:
                if int(req.status) < int(status_gte):
                    continue
            if status_gte is not None and req.status is None:
                continue
            filtered_requests.append(req)
            if len(filtered_requests) >= max_requests:
                break
        next_cursor = min(start + processed_count, total_captured)
        if cursor_value is None:
            state.network_last_call_index = max(state.network_last_call_index, next_cursor)
        has_more = next_cursor < total_captured
        return {
            "requests": _requests_to_dicts(filtered_requests, include_body=include_body),
            "cursor_start": int(start),
            "cursor_next": int(next_cursor),
            "total_captured": int(total_captured),
            "returned": len(filtered_requests),
            "has_more": bool(has_more),
        }
