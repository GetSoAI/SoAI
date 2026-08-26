"""SoAI - MCP utility tool handler: http_request [backend/mcp/tools/http_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx2

from core.network.urls import normalize_http_url
from core.timing.constants import EXTENDED_TIMEOUT_SEC, INTERACTIVE_TIMEOUT_SEC
from core.validation.booleans import parse_bool_flag_with_default
from mcp.tools.argument_fields import require_non_empty_string, require_string
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.http_request_redirects import stream_request_with_local_cookies
from mcp.tools.http_request_response_payload import (
    build_http_response_payload,
    read_response_body_with_limit,
)
from mcp.tools.http_request_retries import (
    build_retry_telemetry,
    bump_attempt,
    parse_http_retry_policy,
    read_retry_after_header,
    record_retry_error,
    record_retry_status,
    require_retryable_request,
    should_retry_for_exception,
    should_retry_for_status,
    sleep_before_retry,
)
from mcp.tools.http_request_sessions import (
    apply_redirect_session_headers,
    apply_session_headers,
    build_updated_session_payload,
    parse_http_session_payload,
)
from mcp.tools.http_request_target_policy import (
    resolve_http_request_target_extensions,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_http_request",)

_DEFAULT_MAX_RESPONSE_BYTES: int = 100_000
_MIN_RESPONSE_BYTES: int = 1_000
_MAX_RESPONSE_BYTES: int = 10_000_000

_VALID_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"},
)
_PLAN_MODE_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})


def _require_plan_mode_safe_request(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    method: str,
    body: str | None,
    session_mode: bool,
) -> None:
    request_context = utility_tools.active_request_context.get()
    if request_context is None:
        return
    agent_mode = request_context.agent_mode
    if not isinstance(agent_mode, str) or agent_mode.strip().lower() != "plan":
        return
    if method not in _PLAN_MODE_SAFE_METHODS:
        raise MCPToolError(
            -32602,
            "http_request in plan mode only allows GET, HEAD, or OPTIONS. Switch to execute mode for mutating HTTP methods.",
        )
    if body is not None:
        raise MCPToolError(
            -32602,
            "http_request in plan mode does not allow request bodies. Switch to execute mode for state-changing HTTP flows.",
        )
    if session_mode:
        raise MCPToolError(
            -32602,
            "http_request in plan mode does not allow session_mode. Switch to execute mode for session-carrying HTTP flows.",
        )


async def tool_http_request(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    url_raw = get_arg(arguments, "url")
    url_raw = require_non_empty_string(
        url_raw,
        key="url",
        type_message="Parameter 'url' must be a non-empty string",
        empty_message="Parameter 'url' must be a non-empty string",
    )
    url = normalize_http_url(url_raw)
    request_extensions = await resolve_http_request_target_extensions(
        utility_tools,
        url=url,
    )

    async def resolve_redirect_extensions(redirect_url: str) -> dict[str, str] | None:
        return await resolve_http_request_target_extensions(
            utility_tools,
            url=redirect_url,
        )

    if not utility_tools.http_client:
        raise MCPToolError(-32603, "HTTP client is not available")

    method_raw = arguments.get("method")
    method = "GET"
    if isinstance(method_raw, str) and method_raw.strip():
        method = method_raw.strip().upper()
    if method not in _VALID_METHODS:
        raise MCPToolError(-32602, f"Invalid HTTP method: {method}")

    headers_raw = arguments.get("headers")
    request_headers: dict[str, str] = {}
    if isinstance(headers_raw, dict):
        for header_key, header_value in headers_raw.items():
            if isinstance(header_key, str) and isinstance(header_value, str):
                request_headers[header_key] = header_value
    caller_request_headers = dict(request_headers)
    session_mode = parse_bool_flag_with_default(arguments.get("session_mode"), default=False)
    if not session_mode and arguments.get("session") is not None:
        raise MCPToolError(-32602, "session is only allowed when session_mode=true")
    session_cookies = None
    session_default_headers: dict[str, str] = {}
    session_per_host_headers: dict[str, dict[str, str]] = {}
    session_payload: JSONDict | None = None
    if session_mode:
        (
            session_cookies,
            session_default_headers,
            session_per_host_headers,
            session_payload,
        ) = parse_http_session_payload(
            arguments.get("session"),
            field_name="session",
            request_url=url,
        )
        request_headers = apply_session_headers(
            url=url,
            session_default_headers=session_default_headers,
            session_per_host_headers=session_per_host_headers,
            request_headers=request_headers,
        )

    def resolve_redirect_headers(redirect_request: httpx2.Request) -> httpx2.Headers:
        if not session_mode:
            return redirect_request.headers
        return apply_redirect_session_headers(
            url=str(redirect_request.url),
            session_default_headers=session_default_headers,
            session_per_host_headers=session_per_host_headers,
            request_headers=caller_request_headers,
            redirect_headers=redirect_request.headers,
        )

    body = arguments.get("body")
    if body is not None:
        body = require_string(
            body,
            key="body",
            type_message="Parameter 'body' must be a string",
        )
    _require_plan_mode_safe_request(
        utility_tools,
        method=method,
        body=body,
        session_mode=session_mode,
    )

    timeout_sec = float(
        parse_int(
            arguments.get("timeout"),
            default=int(float(INTERACTIVE_TIMEOUT_SEC)),
            min_value=1,
            max_value=int(EXTENDED_TIMEOUT_SEC),
        ),
    )

    follow_redirects = parse_bool_flag_with_default(arguments.get("follow_redirects"), default=True)

    max_response_bytes = parse_int(
        arguments.get("max_response_bytes"),
        default=_DEFAULT_MAX_RESPONSE_BYTES,
        min_value=_MIN_RESPONSE_BYTES,
        max_value=_MAX_RESPONSE_BYTES,
    )
    detect_blocked = parse_bool_flag_with_default(arguments.get("detect_blocked"), default=True)
    retry_policy = parse_http_retry_policy(arguments)
    require_retryable_request(
        method=method,
        headers=request_headers,
        policy=retry_policy,
    )
    retry_telemetry = build_retry_telemetry()

    start_monotonic = time.monotonic()

    try:
        last_response_payload: JSONDict | None = None
        attempts_total = int(retry_policy.retries) + 1
        for attempt_index in range(1, attempts_total + 1):
            bump_attempt(retry_telemetry)
            try:
                request_content = body.encode("utf-8") if body else None
                request_cookies = (
                    session_cookies if session_mode and session_cookies is not None else None
                )
                async with stream_request_with_local_cookies(
                    utility_tools.http_client,
                    method=method,
                    url=url,
                    headers=request_headers,
                    content=request_content,
                    timeout=float(timeout_sec),
                    follow_redirects=follow_redirects,
                    cookies=request_cookies,
                    extensions=request_extensions,
                    resolve_extensions=resolve_redirect_extensions,
                    resolve_headers=resolve_redirect_headers,
                ) as response:
                    raw_body, body_truncated = await read_response_body_with_limit(
                        response,
                        max_response_bytes=max_response_bytes,
                    )
                    elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)

                    record_retry_status(retry_telemetry, status_code=int(response.status_code))
                    response_payload: JSONDict = build_http_response_payload(
                        response=response,
                        request_url=url,
                        method=method,
                        elapsed_ms=elapsed_ms,
                        raw_body=raw_body,
                        body_truncated=body_truncated,
                        retry_telemetry=retry_telemetry,
                        detect_blocked=detect_blocked,
                    )
                    if session_mode and session_payload is not None and session_cookies is not None:
                        updated_session_payload = build_updated_session_payload(
                            previous_session_payload=session_payload,
                            session_cookies=session_cookies,
                            response=response,
                        )
                        response_payload["session"] = updated_session_payload
                        session_payload = updated_session_payload
                    last_response_payload = response_payload
                    if attempt_index <= int(retry_policy.retries) and should_retry_for_status(
                        policy=retry_policy,
                        status_code=int(response.status_code),
                    ):
                        await sleep_before_retry(
                            retry_telemetry,
                            policy=retry_policy,
                            attempt_index=attempt_index,
                            retry_after=read_retry_after_header(response),
                        )
                        continue
                    return response_payload
            except (httpx2.TimeoutException, httpx2.RequestError) as exception:
                record_retry_error(
                    retry_telemetry,
                    error=(
                        "timeout_error"
                        if isinstance(exception, httpx2.TimeoutException)
                        else "request_error"
                    ),
                )
                if attempt_index <= int(retry_policy.retries) and should_retry_for_exception(
                    policy=retry_policy,
                    exception=exception,
                ):
                    await sleep_before_retry(
                        retry_telemetry,
                        policy=retry_policy,
                        attempt_index=attempt_index,
                    )
                    continue
                raise
        if last_response_payload is None:
            raise MCPToolError(-32603, "HTTP request failed: no response payload")
        return last_response_payload
    except httpx2.TimeoutException as exception:
        raise MCPToolError(-32603, "HTTP request timed out.") from exception
    except httpx2.RequestError as exception:
        raise MCPToolError(-32603, "HTTP request failed.") from exception
