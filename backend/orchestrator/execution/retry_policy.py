"""SoAI - Orchestrator inference retry policy [backend/orchestrator/execution/retry_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import httpx2

from core.errors.exceptions import ApiError, IpcRemoteRequestError, SoAIError
from core.errors.external_service_exception import ExternalServiceError
from core.openai.provider_error_explanations import (
    UpstreamFailureType,
    resolve_upstream_failure_type,
)
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    normalize_retry_after_header,
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
    headers: Mapping[str, str] | None = (
        exception.headers if isinstance(exception, SoAIError) else None
    )
    if isinstance(exception, httpx2.HTTPStatusError):
        response = exception.response
        if response is not None:
            headers = response.headers
    if headers:
        lowered = {name.lower(): value for name, value in headers.items()}
        guidance = normalize_retry_after_header(lowered.get("retry-after"))
        if guidance is not None:
            return guidance
        guidance = normalize_retry_after_header(lowered.get("retry-after-ms"), milliseconds=True)
        if guidance is not None:
            return guidance
    if isinstance(exception, SoAIError):
        return resolve_upstream_retry_after(exception)
    return None


def _resolve_delay_seconds(exception: Exception, attempt: int) -> float:
    retry_after = _resolve_retry_after_header(exception)
    local_backoff = compute_exponential_backoff_seconds(
        max(0, attempt - 1),
        base_seconds=_BASE_BACKOFF_SECONDS,
        maximum_seconds=_MAX_BACKOFF_SECONDS,
        jitter_ratio=_JITTER_RATIO,
    )
    return max(local_backoff, float(parse_retry_after_seconds(retry_after, round_up=True)))


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
    remaining_seconds: float | None = None,
) -> ExecutionRetryDecision:
    failure_type = (
        resolve_upstream_failure_type(exception.details or {})
        if isinstance(exception, SoAIError)
        else None
    )
    if failure_type is not None and failure_type not in {
        UpstreamFailureType.RATE_LIMIT,
        UpstreamFailureType.TIMEOUT,
        UpstreamFailureType.PROVIDER_OUTAGE,
    }:
        return ExecutionRetryDecision(False, 1, 0.0, "not_retryable")
    if failure_type is UpstreamFailureType.RATE_LIMIT or (
        failure_type is None and _is_provider_rate_limit(exception)
    ):
        should_retry = attempt < PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS
        delay = _resolve_delay_seconds(exception, attempt)
        return ExecutionRetryDecision(
            should_retry=should_retry and (remaining_seconds is None or delay < remaining_seconds),
            max_attempts=PROVIDER_RATE_LIMIT_RETRY_ATTEMPTS,
            delay_seconds=delay,
            reason="provider_rate_limited",
        )
    if failure_type in {UpstreamFailureType.TIMEOUT, UpstreamFailureType.PROVIDER_OUTAGE} or (
        failure_type is None and _is_default_retryable(exception)
    ):
        should_retry = attempt < DEFAULT_EXECUTION_RETRY_ATTEMPTS
        delay = _resolve_delay_seconds(exception, attempt)
        return ExecutionRetryDecision(
            should_retry=should_retry and (remaining_seconds is None or delay < remaining_seconds),
            max_attempts=DEFAULT_EXECUTION_RETRY_ATTEMPTS,
            delay_seconds=delay,
            reason="transient_inference_failure",
        )
    return ExecutionRetryDecision(
        should_retry=False,
        max_attempts=1,
        delay_seconds=0.0,
        reason="not_retryable",
    )
