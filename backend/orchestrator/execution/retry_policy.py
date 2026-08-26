"""SoAI - Orchestrator inference retry policy [backend/orchestrator/execution/retry_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from core.errors.exceptions import ApiError, IpcRemoteRequestError
from core.errors.external_service_exception import ExternalServiceError
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    parse_retry_after_seconds,
)
from orchestrator.execution.upstream_error_metadata import (
    is_upstream_transport_error,
    resolve_upstream_http_status,
    resolve_upstream_retry_after,
)

__all__ = (
    "DEFAULT_EXECUTION_RETRY_ATTEMPTS",
    "PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS",
    "ExecutionRetryDecision",
    "resolve_execution_retry_decision",
    "resolve_max_execution_attempts",
)

DEFAULT_EXECUTION_RETRY_ATTEMPTS = 3
PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS = 10
_BASE_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 30.0
_JITTER_RATIO = 0.2


@dataclass(frozen=True, slots=True)
class ExecutionRetryDecision:
    should_retry: bool
    max_attempts: int
    delay_seconds: float
    reason: str


def _resolve_retry_after_header(exception: Exception) -> str | None:
    if isinstance(exception, httpx2.HTTPStatusError):
        response = exception.response
        if response is not None:
            value = response.headers.get("Retry-After")
            return value.strip() if isinstance(value, str) and value.strip() else None
    if isinstance(exception, ExternalServiceError | IpcRemoteRequestError):
        if exception.headers is not None:
            value = exception.headers.get("Retry-After")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return resolve_upstream_retry_after(exception)
    if isinstance(exception, ApiError) and exception.headers is not None:
        value = exception.headers.get("Retry-After")
        return value.strip() if isinstance(value, str) and value.strip() else None
    return None


def _resolve_delay_seconds(exception: Exception, attempt: int) -> float:
    retry_after = _resolve_retry_after_header(exception)
    if retry_after is not None:
        return float(
            min(
                int(_MAX_BACKOFF_SECONDS),
                parse_retry_after_seconds(
                    retry_after,
                    default_seconds=int(_BASE_BACKOFF_SECONDS),
                ),
            ),
        )
    return compute_exponential_backoff_seconds(
        max(0, attempt - 1),
        base_seconds=_BASE_BACKOFF_SECONDS,
        maximum_seconds=_MAX_BACKOFF_SECONDS,
        jitter_ratio=_JITTER_RATIO,
    )


def _is_provider_rate_limit(exception: Exception) -> bool:
    if isinstance(exception, httpx2.HTTPStatusError):
        response = exception.response
        return response is not None and response.status_code == 429
    if isinstance(exception, ExternalServiceError | IpcRemoteRequestError):
        return resolve_upstream_http_status(exception) == 429
    if isinstance(exception, ApiError):
        return exception.http_status == 429
    return False


def _is_default_retryable(exception: Exception) -> bool:
    if isinstance(exception, httpx2.HTTPStatusError):
        response = exception.response
        if response is None:
            return True
        return response.status_code >= 500
    if isinstance(exception, ExternalServiceError | IpcRemoteRequestError):
        upstream_status = resolve_upstream_http_status(exception)
        if upstream_status is not None:
            return upstream_status >= 500
        return is_upstream_transport_error(exception)
    if isinstance(exception, ApiError):
        return exception.http_status >= 500
    return isinstance(exception, httpx2.RequestError)


def resolve_max_execution_attempts() -> int:
    return max(DEFAULT_EXECUTION_RETRY_ATTEMPTS, PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS)


def resolve_execution_retry_decision(
    exception: Exception,
    *,
    attempt: int,
) -> ExecutionRetryDecision:
    if _is_provider_rate_limit(exception):
        should_retry = attempt < PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS
        return ExecutionRetryDecision(
            should_retry=should_retry,
            max_attempts=PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS,
            delay_seconds=_resolve_delay_seconds(exception, attempt),
            reason="provider_rate_limited",
        )
    if _is_default_retryable(exception):
        should_retry = attempt < DEFAULT_EXECUTION_RETRY_ATTEMPTS
        return ExecutionRetryDecision(
            should_retry=should_retry,
            max_attempts=DEFAULT_EXECUTION_RETRY_ATTEMPTS,
            delay_seconds=_resolve_delay_seconds(exception, attempt),
            reason="transient_inference_failure",
        )
    return ExecutionRetryDecision(
        should_retry=False,
        max_attempts=1,
        delay_seconds=0.0,
        reason="not_retryable",
    )
