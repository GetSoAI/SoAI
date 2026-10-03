"""SoAI - Bounded HTTP transfer retry decisions [backend/core/network/transfer_retry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from typing import Literal

import httpx
import httpx2

from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.errors import NetworkPolicyResolutionError
from core.network.protocols import DownloadInterruptionProtocol
from core.network.urls import redact_url_for_logging
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    parse_retry_after_milliseconds,
)
from core.validation.strict_numbers import (
    require_finite_float_strict,
    require_positive_int_strict,
)

__all__ = (
    "build_http_transfer_retry_policy",
    "HTTP_TRANSFER_EXCEPTIONS",
    "HTTP_TRANSFER_CLEANUP_EXCEPTIONS",
    "HTTPTransferRetryPolicy",
    "HTTPTransferAttempts",
    "is_retryable_http_failure",
    "wait_for_transfer_retry",
)

HTTP_TRANSFER_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx2.HTTPError,
    httpx.HTTPError,
    NetworkPolicyResolutionError,
)
HTTP_TRANSFER_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    *HTTP_TRANSFER_EXCEPTIONS,
)
RETRYABLE_HTTP_STATUSES = frozenset((408, 429, 500, 502, 503, 504))
LOGGER_NAME = "SoAI.core.network.transfer_retry"


@dataclass(frozen=True, slots=True)
class HTTPTransferRetryPolicy:
    attempts: int
    initial_delay: float
    maximum_delay: float
    io_timeout: float
    maximum_retry_after: float
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        require_positive_int_strict(self.attempts, error_message="Retry attempts must be positive.")
        for value in (
            self.initial_delay,
            self.maximum_delay,
            self.io_timeout,
            self.maximum_retry_after,
        ):
            validated = require_finite_float_strict(
                value, error_message="Retry limits must be finite positive numbers."
            )
            if validated <= 0:
                raise ValidationError("Retry limits must be finite positive numbers.")
        jitter = require_finite_float_strict(
            self.jitter_ratio, error_message="Retry jitter must be between zero and one."
        )
        if not 0 <= jitter <= 1 or self.initial_delay > self.maximum_delay:
            raise ValidationError("Invalid HTTP retry delay configuration.")

    def bounded_timeout(self, timeout: float) -> float:
        validated = require_finite_float_strict(
            timeout, error_message="HTTP timeout must be finite and positive."
        )
        if validated <= 0:
            raise ValidationError("HTTP timeout must be finite and positive.")
        return min(validated, self.io_timeout)


def build_http_transfer_retry_policy(
    profile: Literal["artifact", "interactive", "metadata"],
) -> HTTPTransferRetryPolicy:
    if profile == "artifact":
        return HTTPTransferRetryPolicy(10, 1.0, 60.0, 60.0, 300.0)
    if profile == "interactive":
        return HTTPTransferRetryPolicy(3, 0.5, 2.0, 20.0, 2.0)
    if profile == "metadata":
        return HTTPTransferRetryPolicy(5, 1.0, 8.0, 20.0, 300.0)
    raise ValidationError("Unknown HTTP transfer retry profile.")


async def wait_for_transfer_retry(
    delay: float,
    *,
    interruption: DownloadInterruptionProtocol | None,
) -> None:
    if interruption is None:
        await asyncio.sleep(delay)
        return
    interruption.raise_if_cancelled()
    try:
        await asyncio.wait_for(interruption.wait(), timeout=delay)
    except TimeoutError:
        interruption.raise_if_cancelled()
    interruption.raise_if_cancelled()


def _http_status_failure(
    exception: BaseException,
) -> httpx2.HTTPStatusError | httpx.HTTPStatusError | None:
    current: BaseException | None = exception
    visited: set[int] = set()
    while isinstance(current, httpx2.HTTPError | httpx.HTTPError):
        if id(current) in visited:
            return None
        visited.add(id(current))
        if isinstance(current, httpx2.HTTPStatusError | httpx.HTTPStatusError):
            return current
        current = current.__cause__
    return None


def is_retryable_http_failure(exception: BaseException) -> bool:
    pending = [exception]
    visited: set[int] = set()
    while pending:
        cause = pending.pop()
        if id(cause) in visited:
            continue
        visited.add(id(cause))
        if isinstance(cause, ssl.SSLCertVerificationError):
            return False
        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
        if cause.__context__ is not None:
            pending.append(cause.__context__)
    status_failure = _http_status_failure(exception)
    if status_failure is not None:
        return status_failure.response.status_code in RETRYABLE_HTTP_STATUSES
    return isinstance(
        exception,
        NetworkPolicyResolutionError
        | httpx2.TimeoutException
        | httpx2.ConnectError
        | httpx2.ReadError
        | httpx2.WriteError
        | httpx2.RemoteProtocolError
        | httpx.TimeoutException
        | httpx.ConnectError
        | httpx.ReadError
        | httpx.WriteError
        | httpx.RemoteProtocolError,
    )


class HTTPTransferAttempts:
    def __init__(self, policy: HTTPTransferRetryPolicy, *, url: str) -> None:
        self.policy = policy
        self.url = url
        self.started = 0

    def start(self) -> None:
        if self.started >= self.policy.attempts:
            raise ValidationError("The HTTP transfer attempt budget is exhausted.")
        self.started += 1

    def retry_delay(self, exception: BaseException) -> float | None:
        if self.started >= self.policy.attempts or not is_retryable_http_failure(exception):
            return None
        retry_after = 0.0
        status_failure = _http_status_failure(exception)
        if status_failure is not None:
            retry_after = (
                parse_retry_after_milliseconds(
                    status_failure.response.headers.get("Retry-After"),
                    default_milliseconds=0,
                    maximum_milliseconds=int(self.policy.maximum_retry_after * 1000) + 1,
                )
                / 1000.0
            )
        if retry_after > self.policy.maximum_retry_after:
            return None
        delay = max(
            retry_after,
            compute_exponential_backoff_seconds(
                self.started - 1,
                base_seconds=self.policy.initial_delay,
                maximum_seconds=self.policy.maximum_delay,
                jitter_ratio=self.policy.jitter_ratio,
            ),
        )
        get_logger(LOGGER_NAME).warning(
            "HTTP transfer retry %s/%s in %.3fs after %s: %s",
            self.started + 1,
            self.policy.attempts,
            delay,
            type(exception).__name__,
            redact_url_for_logging(self.url),
        )
        return delay
