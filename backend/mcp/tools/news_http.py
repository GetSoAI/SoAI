"""SoAI - MCP news provider HTTP fetch with rate gating and retries [backend/mcp/tools/news_http.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import RateLimitError
from core.errors.external_service_exception import ExternalServiceError
from mcp.tools.error import MCPToolError
from mcp.tools.http_request_retries import (
    HttpRetryPolicy,
    build_retry_telemetry,
    bump_attempt,
    record_retry_error,
    record_retry_status,
    should_retry_for_exception,
    should_retry_for_status,
    sleep_before_retry,
)
from mcp.tools.provider_http import (
    build_provider_http_status_message,
    map_provider_http_exception,
    parse_provider_json_dict,
    read_provider_response_bytes,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("fetch_news_provider_payload",)

_NEWS_PROVIDER_HEADERS: tuple[tuple[str, str], ...] = (
    ("Accept", "application/json"),
    ("User-Agent", "SoAI/1.0 news tool"),
)
_RATE_LIMIT_BODY_MARKERS: tuple[str, ...] = (
    "please limit requests",
    "too many requests",
    "rate limit",
)


def _build_news_retry_policy() -> HttpRetryPolicy:
    return HttpRetryPolicy(
        retries=3,
        backoff_min_ms=8000,
        backoff_max_ms=24000,
        jitter_max_ms=1500,
        retry_on_status=frozenset({502, 503, 504}),
        retry_on_timeouts=True,
        retry_on_request_errors=True,
    )


def _build_provider_status_error(status_code: int) -> str:
    return build_provider_http_status_message(
        status_code,
        provider_label="News provider",
        rate_limit_message="News provider rate limit was reached. Retry later.",
        unavailable_message="News provider is temporarily unavailable.",
    )


def _body_contains_rate_limit(body: bytes) -> bool:
    body_text_lower = body.decode("utf-8", errors="replace").lower()
    return any(marker in body_text_lower for marker in _RATE_LIMIT_BODY_MARKERS)


def _map_request_exception(exception: httpx2.HTTPError) -> MCPToolError:
    return map_provider_http_exception(
        exception,
        timeout_message="News provider timed out while processing the request.",
        request_failed_message="News provider request failed.",
    )


async def _read_provider_response(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
    extensions: dict[str, str] | None,
    timeout_sec: float,
    max_response_bytes: int,
) -> tuple[bytes, int, str | None]:
    return await read_provider_response_bytes(
        utility_tools,
        url=url,
        extensions=extensions,
        timeout_sec=timeout_sec,
        max_response_bytes=max_response_bytes,
        exceeded_size_message="News provider response exceeded size limit.",
        headers=dict(_NEWS_PROVIDER_HEADERS),
    )


def _parse_provider_body(body: bytes) -> JSONDict:
    try:
        return parse_provider_json_dict(
            body,
            field="news provider response",
            invalid_message="News provider returned an unexpected response. Retry later.",
        )
    except MCPToolError as exception:
        raise ExternalServiceError(
            "News provider returned an unexpected response. Retry later.",
        ) from exception


async def fetch_news_provider_payload(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
    query_key: str,
    extensions: dict[str, str] | None,
    timeout_sec: float,
    max_response_bytes: int,
) -> JSONDict:
    telemetry = build_retry_telemetry()
    retry_policy = _build_news_retry_policy()
    attempts_total = retry_policy.retries + 1
    for attempt_index in range(1, attempts_total + 1):
        bump_attempt(telemetry)
        retry_status_code: int | None = None
        try:
            async with utility_tools.news_provider_control.request_slot(query_key):
                try:
                    body, status_code, retry_after = await _read_provider_response(
                        utility_tools,
                        url=url,
                        extensions=extensions,
                        timeout_sec=timeout_sec,
                        max_response_bytes=max_response_bytes,
                    )
                except httpx2.HTTPError:
                    utility_tools.news_provider_control.record_transient_failure(query_key)
                    raise
                except MCPToolError as exception:
                    utility_tools.news_provider_control.record_transient_failure(query_key)
                    raise ExternalServiceError(exception.message) from exception
                record_retry_status(telemetry, status_code=status_code)
                if 200 <= status_code < 300:
                    try:
                        payload = _parse_provider_body(body)
                    except ExternalServiceError as exception:
                        if _body_contains_rate_limit(body):
                            utility_tools.news_provider_control.record_rate_limit(
                                query_key,
                                retry_after,
                            )
                            raise RateLimitError(_build_provider_status_error(429)) from exception
                        utility_tools.news_provider_control.record_transient_failure(query_key)
                        raise
                    if not isinstance(payload.get("articles"), list) and _body_contains_rate_limit(
                        body
                    ):
                        utility_tools.news_provider_control.record_rate_limit(
                            query_key,
                            retry_after,
                        )
                        raise RateLimitError(_build_provider_status_error(429))
                    utility_tools.news_provider_control.record_success(query_key)
                    return payload
                if status_code == 429:
                    utility_tools.news_provider_control.record_rate_limit(query_key, retry_after)
                    raise RateLimitError(_build_provider_status_error(status_code))
                if attempt_index <= retry_policy.retries and should_retry_for_status(
                    policy=retry_policy,
                    status_code=status_code,
                ):
                    utility_tools.news_provider_control.record_transient_failure(query_key)
                    retry_status_code = status_code
                if retry_status_code is None and (status_code == 408 or status_code >= 500):
                    utility_tools.news_provider_control.record_transient_failure(query_key)
                    raise ExternalServiceError(_build_provider_status_error(status_code))
                if retry_status_code is None:
                    utility_tools.news_provider_control.record_success(query_key)
                    raise MCPToolError(-32603, _build_provider_status_error(status_code))
        except httpx2.HTTPError as exception:
            record_retry_error(telemetry, error=str(exception))
            if attempt_index <= retry_policy.retries and should_retry_for_exception(
                policy=retry_policy,
                exception=exception,
            ):
                await sleep_before_retry(
                    telemetry,
                    policy=retry_policy,
                    attempt_index=attempt_index,
                )
                continue
            mapped = _map_request_exception(exception)
            raise ExternalServiceError(mapped.message) from exception
        if retry_status_code is not None:
            await sleep_before_retry(
                telemetry,
                policy=retry_policy,
                attempt_index=attempt_index,
            )
            continue
    raise ExternalServiceError("News provider request failed.")
