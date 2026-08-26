"""SoAI - Messaging account runtime task registry and retry state [backend/app/background/messaging_runtime_task_set.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.messaging.observability_emission import (
    log_messaging_bounded_failure,
    log_messaging_diagnostic,
    log_messaging_lifecycle,
)
from core.messaging.observability_fields import MessagingLogFields
from core.tasks.progress import await_background_task_shutdown
from core.timing.monotonic import monotonic_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform

__all__ = ("MessagingRuntimeSignature", "MessagingRuntimeTaskSet")

LOGGER_NAME = "SoAI.app.background.messaging_runtime_task_set"
OPERATION_RUNTIME = "messaging.account.runtime"
FAILURE_SUMMARY_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class MessagingRuntimeSignature:
    revision: int
    lifecycle_generation: int
    configuration_fingerprint: str


@dataclass(frozen=True, slots=True)
class _MessagingRuntimeEntry:
    task: asyncio.Task[None]
    platform: MessagingPlatform
    signature: MessagingRuntimeSignature


@dataclass(slots=True)
class _MessagingRuntimeRetry:
    signature: MessagingRuntimeSignature
    attempt: int
    next_attempt_ms: int
    limiter: RateLimitedLogger


class MessagingRuntimeTaskSet:
    def __init__(self) -> None:
        self._entries: dict[str, _MessagingRuntimeEntry] = {}
        self._retries: dict[str, _MessagingRuntimeRetry] = {}

    def account_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self._entries, *self._retries)))

    def has_task(self, account_id: str) -> bool:
        return account_id in self._entries

    def is_current(
        self,
        account_id: str,
        signature: MessagingRuntimeSignature,
        *,
        completed_is_healthy: bool,
    ) -> bool:
        entry = self._entries.get(account_id)
        if entry is None or entry.signature != signature:
            return False
        if not entry.task.done():
            return True
        return (
            completed_is_healthy and not entry.task.cancelled() and entry.task.exception() is None
        )

    def retry_is_due(
        self,
        account_id: str,
        signature: MessagingRuntimeSignature,
    ) -> bool:
        retry = self._retries.get(account_id)
        if retry is None or retry.signature != signature:
            return True
        return monotonic_ms() >= retry.next_attempt_ms

    def pop_completed_failure(
        self,
        account_id: str,
        signature: MessagingRuntimeSignature,
    ) -> Exception | None:
        entry = self._entries.get(account_id)
        if (
            entry is None
            or entry.signature != signature
            or not entry.task.done()
            or entry.task.cancelled()
        ):
            return None
        exception = entry.task.exception()
        if exception is None:
            return None
        self._entries.pop(account_id)
        if isinstance(exception, Exception):
            return exception
        raise exception

    def register(
        self,
        *,
        account_id: str,
        platform: MessagingPlatform,
        signature: MessagingRuntimeSignature,
        task: asyncio.Task[None],
    ) -> None:
        self._entries[account_id] = _MessagingRuntimeEntry(
            task=task,
            platform=platform,
            signature=signature,
        )
        self._retries.pop(account_id, None)
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message="Messaging account runtime started.",
            log_fields=MessagingLogFields(
                operation=OPERATION_RUNTIME,
                platform=platform,
                phase="complete",
                outcome="success",
                account_id=account_id,
                revision=signature.revision,
                lifecycle_generation=signature.lifecycle_generation,
            ),
        )

    def defer_failure(
        self,
        *,
        account_id: str,
        platform: MessagingPlatform,
        signature: MessagingRuntimeSignature,
        failure_code: str,
    ) -> int:
        previous = self._retries.get(account_id)
        attempt = (
            previous.attempt + 1 if previous is not None and previous.signature == signature else 0
        )
        delay = compute_exponential_backoff_seconds(
            attempt,
            base_seconds=1.0,
            maximum_seconds=60.0,
            jitter_ratio=0.2,
        )
        limiter = (
            previous.limiter
            if previous is not None and previous.signature == signature
            else RateLimitedLogger(interval_seconds=FAILURE_SUMMARY_INTERVAL_SECONDS)
        )
        retry_after_ms = int(delay * 1000)
        self._retries[account_id] = _MessagingRuntimeRetry(
            signature=signature,
            attempt=attempt,
            next_attempt_ms=monotonic_ms() + retry_after_ms,
            limiter=limiter,
        )
        log_messaging_bounded_failure(
            get_logger(LOGGER_NAME),
            limiter,
            message="Messaging account runtime start keeps failing.",
            log_fields=MessagingLogFields(
                operation=OPERATION_RUNTIME,
                platform=platform,
                phase="complete",
                outcome="retryable",
                account_id=account_id,
                revision=signature.revision,
                lifecycle_generation=signature.lifecycle_generation,
                attempt=attempt,
                failure_code=failure_code,
                retry_after_ms=retry_after_ms,
            ),
        )
        return retry_after_ms

    async def stop(self, account_id: str, *, superseded: bool) -> None:
        entry = self._entries.pop(account_id, None)
        self._retries.pop(account_id, None)
        if entry is None:
            return
        await await_background_task_shutdown(
            entry.task,
            logger=get_logger(LOGGER_NAME),
            operation="messaging.account.runtime_stop",
            message="Messaging account runtime shutdown failed.",
            level="warning",
            metadata={"account_id": account_id},
        )
        fields = MessagingLogFields(
            operation=OPERATION_RUNTIME,
            platform=entry.platform,
            phase="complete",
            outcome="superseded" if superseded else "success",
            account_id=account_id,
            revision=entry.signature.revision,
            lifecycle_generation=entry.signature.lifecycle_generation,
        )
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message=(
                "Messaging account runtime was superseded."
                if superseded
                else "Messaging account runtime stopped."
            ),
            log_fields=fields,
        )
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Messaging account runtime task finalized.",
            log_fields=replace(fields, outcome_detail="task_finalized"),
        )
