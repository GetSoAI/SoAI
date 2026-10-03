"""SoAI - Bounded idempotent HTTP metadata reads [backend/core/network/retryable_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.network.errors import HTTPReadUnavailableError
from core.network.transfer_retry import (
    HTTP_TRANSFER_EXCEPTIONS,
    HTTPTransferAttempts,
    build_http_transfer_retry_policy,
    is_retryable_http_failure,
    wait_for_transfer_retry,
)

__all__ = ("run_retryable_http_read",)


class _ReadInterruption:
    def __init__(self, shutdown_event: asyncio.Event | None) -> None:
        self.shutdown_event = shutdown_event

    def raise_if_cancelled(self) -> None:
        if self.shutdown_event is not None and self.shutdown_event.is_set():
            raise asyncio.CancelledError("HTTP metadata read cancelled.")

    async def wait(self) -> None:
        if self.shutdown_event is None:
            await asyncio.Event().wait()
        else:
            await self.shutdown_event.wait()


async def run_retryable_http_read[Result](
    read: Callable[[float], Result],
    *,
    url: str,
    shutdown_event: asyncio.Event | None = None,
) -> Result:
    attempts = HTTPTransferAttempts(build_http_transfer_retry_policy("metadata"), url=url)
    interruption = _ReadInterruption(shutdown_event)
    while True:
        interruption.raise_if_cancelled()
        attempts.start()
        try:
            result = await run_joined_thread_call(
                read,
                attempts.policy.io_timeout,
                task_name="http-metadata-read",
                retain_resources_until_complete=True,
            )
        except HTTP_TRANSFER_EXCEPTIONS as exception:
            interruption.raise_if_cancelled()
            delay = attempts.retry_delay(exception)
            if delay is None:
                if is_retryable_http_failure(exception):
                    raise HTTPReadUnavailableError(
                        "The metadata source is temporarily unavailable. Retry later."
                    ) from exception
                raise
            await wait_for_transfer_retry(delay, interruption=interruption)
            continue
        interruption.raise_if_cancelled()
        return result
