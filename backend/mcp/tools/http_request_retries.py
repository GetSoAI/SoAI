"""SoAI - HTTP request retry policy [backend/mcp/tools/http_request_retries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx2

from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.booleans import parse_bool_flag_with_default
from core.validation.integers import is_strict_int
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "HttpRetryPolicy",
    "build_retry_telemetry",
    "bump_attempt",
    "compute_retry_delay_ms",
    "parse_http_retry_policy",
    "require_retryable_request",
    "record_retry_error",
    "record_retry_status",
    "read_retry_after_header",
    "should_retry_for_exception",
    "should_retry_for_status",
    "sleep_before_retry",
)

_MAX_RETRIES: int = 10
_MIN_BACKOFF_MS: int = 10
_MAX_BACKOFF_MS: int = 60_000
_MAX_JITTER_MS: int = 10_000


@dataclass(frozen=True, slots=True)
class HttpRetryPolicy:
    retries: int
    backoff_min_ms: int
    backoff_max_ms: int
    jitter_max_ms: int
    retry_on_status: frozenset[int]
    retry_on_timeouts: bool
    retry_on_request_errors: bool


def parse_http_retry_policy(arguments: JSONDict) -> HttpRetryPolicy:
    retries = parse_int(arguments.get("retries"), default=0, min_value=0, max_value=_MAX_RETRIES)
    backoff_min_ms = parse_int(
        arguments.get("retry_backoff_min_ms"),
        default=250,
        min_value=_MIN_BACKOFF_MS,
        max_value=_MAX_BACKOFF_MS,
    )
    backoff_max_ms = parse_int(
        arguments.get("retry_backoff_max_ms"),
        default=10_000,
        min_value=_MIN_BACKOFF_MS,
        max_value=_MAX_BACKOFF_MS,
    )
    if backoff_max_ms < backoff_min_ms:
        raise MCPToolError(
            -32602,
            "retry_backoff_max_ms must be >= retry_backoff_min_ms",
        )
    jitter_max_ms = parse_int(
        arguments.get("retry_jitter_max_ms"),
        default=250,
        min_value=0,
        max_value=_MAX_JITTER_MS,
    )
    retry_on_timeouts = parse_bool_flag_with_default(
        arguments.get("retry_on_timeouts"),
        default=True,
    )
    retry_on_request_errors = parse_bool_flag_with_default(
        arguments.get("retry_on_request_errors"),
        default=True,
    )
    retry_on_status = _parse_retry_statuses(arguments.get("retry_on_status"))
    if retry_on_status is None:
        retry_on_status = frozenset({429, 502, 503, 504})
    return HttpRetryPolicy(
        retries=retries,
        backoff_min_ms=backoff_min_ms,
        backoff_max_ms=backoff_max_ms,
        jitter_max_ms=jitter_max_ms,
        retry_on_status=retry_on_status,
        retry_on_timeouts=retry_on_timeouts,
        retry_on_request_errors=retry_on_request_errors,
    )


def build_retry_telemetry() -> JSONDict:
    return {"attempts": 0, "delays_ms": [], "errors": [], "status_codes": []}


def record_retry_status(telemetry: JSONDict, *, status_code: int) -> None:
    _append_int_list(telemetry, "status_codes", status_code)


def record_retry_error(telemetry: JSONDict, *, error: str) -> None:
    _append_str_list(telemetry, "errors", error)


def bump_attempt(telemetry: JSONDict) -> None:
    attempts_raw = telemetry.get("attempts")
    if not is_strict_int(attempts_raw):
        telemetry["attempts"] = 1
        return
    telemetry["attempts"] = int(attempts_raw) + 1


async def sleep_before_retry(
    telemetry: JSONDict,
    *,
    policy: HttpRetryPolicy,
    attempt_index: int,
    retry_after: str | None = None,
) -> None:
    delay_ms = compute_retry_delay_ms(
        policy=policy,
        attempt_index=attempt_index,
        retry_after=retry_after,
    )
    _append_int_list(telemetry, "delays_ms", delay_ms)
    await asyncio.sleep(float(delay_ms) / 1000.0)


def compute_retry_delay_ms(
    *,
    policy: HttpRetryPolicy,
    attempt_index: int,
    retry_after: str | None = None,
    now_epoch_seconds: float | None = None,
) -> int:
    if attempt_index < 1:
        raise MCPToolError(-32603, "Internal error: attempt_index must be >= 1")
    retry_after_ms = _parse_retry_after_ms(
        retry_after,
        now_epoch_seconds=(time.time() if now_epoch_seconds is None else now_epoch_seconds),
    )
    if retry_after_ms is not None:
        return min(retry_after_ms, policy.backoff_max_ms)
    exponent = attempt_index - 1
    delay_seconds = compute_exponential_backoff_seconds(
        exponent,
        base_seconds=float(policy.backoff_min_ms) / 1000.0,
        maximum_seconds=float(policy.backoff_max_ms) / 1000.0,
        jitter_seconds=float(policy.jitter_max_ms) / 1000.0,
    )
    return int(delay_seconds * 1000.0)


def should_retry_for_status(*, policy: HttpRetryPolicy, status_code: int) -> bool:
    return int(status_code) in policy.retry_on_status


def should_retry_for_exception(*, policy: HttpRetryPolicy, exception: BaseException) -> bool:
    if isinstance(exception, httpx2.TimeoutException):
        return bool(policy.retry_on_timeouts)
    if isinstance(exception, httpx2.RequestError):
        return bool(policy.retry_on_request_errors)
    return False


def require_retryable_request(
    *,
    method: str,
    headers: dict[str, str],
    policy: HttpRetryPolicy,
) -> None:
    if policy.retries <= 0 or method in {"GET", "HEAD", "OPTIONS"}:
        return
    idempotency_values = [
        value.strip() for key, value in headers.items() if key.strip().lower() == "idempotency-key"
    ]
    if not idempotency_values or any(not value for value in idempotency_values):
        raise MCPToolError(
            -32602,
            "Retries for mutating HTTP methods require a non-empty Idempotency-Key header.",
        )
    if len(idempotency_values) != 1:
        raise MCPToolError(
            -32602,
            "Retries for mutating HTTP methods require exactly one Idempotency-Key header.",
        )


def read_retry_after_header(response: httpx2.Response) -> str | None:
    headers = response.headers
    try:
        value = headers.get("retry-after")
    except AttributeError:
        value = None
    if isinstance(value, str):
        return value
    try:
        raw_headers = headers.raw
    except AttributeError:
        return None
    for key, raw_value in raw_headers:
        if key.lower() == b"retry-after":
            return raw_value.decode("latin-1")
    return None


def _parse_retry_after_ms(value: str | None, *, now_epoch_seconds: float) -> int | None:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return None
    try:
        seconds = int(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.utcoffset() is None:
            return None
        seconds = int(parsed.timestamp() - now_epoch_seconds)
    if seconds < 0:
        return None
    return seconds * 1000


def _parse_retry_statuses(raw: JSONValue) -> frozenset[int] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise MCPToolError(-32602, "retry_on_status must be an array of integers")
    values: set[int] = set()
    for index, item in enumerate(raw):
        if not is_strict_int(item):
            raise MCPToolError(-32602, f"retry_on_status[{index}] must be an integer")
        if item < 100 or item > 599:
            raise MCPToolError(-32602, f"retry_on_status[{index}] must be between 100 and 599")
        values.add(int(item))
    return frozenset(values)


def _append_int_list(target: JSONDict, key: str, value: int) -> None:
    raw = target.get(key)
    if raw is None:
        target[key] = [int(value)]
        return
    if not isinstance(raw, list):
        target[key] = [int(value)]
        return
    raw.append(int(value))


def _append_str_list(target: JSONDict, key: str, value: str) -> None:
    raw = target.get(key)
    if raw is None:
        target[key] = [str(value)]
        return
    if not isinstance(raw, list):
        target[key] = [str(value)]
        return
    raw.append(str(value))
