"""SoAI - Request deduplication cache with hash-based waiter futures [backend/orchestrator/queueing/deduplication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.tasks.orchestration_context import OrchestrationContext
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from orchestrator.queueing.deduplication_hash import calculate_dedup_hash

if TYPE_CHECKING:
    from core.orchestrator.routing_config import RoutingConfig
    from core.types.json import JSONDict

__all__ = (
    "DedupRegistrationResult",
    "QueueDeduplication",
    "QueueDeduplicationConfig",
)

LOGGER_NAME = "SoAI.orchestrator.queueing.deduplication"
RESOLUTION_OWNERSHIP_TIMEOUT_SECONDS = 1800.0
RECOVERY_RETRY_BASE_SECONDS = 300.0
RECOVERY_RETRY_MAXIMUM_SECONDS = 3600.0
RECOVERY_RETRY_JITTER_RATIO = 0.2


@dataclass(frozen=True, slots=True)
class QueueDeduplicationConfig:
    enabled: bool
    waiter_ttl_seconds: float


@dataclass(frozen=True, slots=True)
class DedupRegistrationResult:
    is_waiter: bool
    lead_task_id: str | None = None


class QueueDeduplication:
    def __init__(self, config: QueueDeduplicationConfig) -> None:
        self._config = config
        self.enabled = config.enabled
        self._lock = asyncio.Lock()
        self._waiters: defaultdict[str, list[str]] = defaultdict(list)
        self._futures: dict[str, asyncio.Future[JSONDict | None]] = {}
        self._lead_task_ids: dict[str, str] = {}
        self._registered_at: dict[str, float] = {}
        self._resolving_waiters: dict[str, float] = {}
        self._recovery_waiters: set[str] = set()
        self._recovery_attempts: dict[str, int] = {}
        self._recovery_available_at: dict[str, float] = {}

    def apply_config(self, config: QueueDeduplicationConfig) -> bool:
        previous = self._config
        self._config = config
        self.enabled = config.enabled
        return previous.enabled != config.enabled

    async def get_deduplicated_count(self) -> int:
        async with self._lock:
            waiter_ids = set(self._resolving_waiters)
            waiter_ids.update(self._recovery_waiters)
            for waiters in self._waiters.values():
                waiter_ids.update(waiters)
            return len(waiter_ids)

    def calculate_dedup_hash(
        self,
        context: OrchestrationContext,
        *,
        routing_config: RoutingConfig,
    ) -> str:
        return calculate_dedup_hash(context, routing_config=routing_config)

    async def register_or_reuse(self, *, dedup_hash: str, task_id: str) -> DedupRegistrationResult:
        if not dedup_hash or not task_id:
            return DedupRegistrationResult(is_waiter=False)
        async with self._lock:
            if dedup_hash in self._futures:
                future = self._futures[dedup_hash]
                if not future.done():
                    self._waiters[dedup_hash].append(task_id)
                    return DedupRegistrationResult(
                        is_waiter=True,
                        lead_task_id=self._lead_task_ids.get(dedup_hash),
                    )
                return DedupRegistrationResult(is_waiter=False)
            self._waiters[dedup_hash] = []
            self._futures[dedup_hash] = asyncio.get_running_loop().create_future()
            self._lead_task_ids[dedup_hash] = task_id
            self._registered_at[dedup_hash] = time.monotonic()
            return DedupRegistrationResult(is_waiter=False, lead_task_id=task_id)

    async def remove_waiter(self, *, dedup_hash: str, task_id: str) -> None:
        if not dedup_hash or not task_id:
            return
        async with self._lock:
            waiters = self._waiters.get(dedup_hash)
            if waiters:
                self._waiters[dedup_hash] = [
                    waiter_task_id for waiter_task_id in waiters if waiter_task_id != task_id
                ]
            self._resolving_waiters.pop(task_id, None)
            self._recovery_waiters.discard(task_id)
            self._recovery_attempts.pop(task_id, None)
            self._recovery_available_at.pop(task_id, None)

    async def drain_waiters(self, *, reason: str) -> set[str]:
        waiter_ids: set[str] = set()
        async with self._lock:
            for hash_key, waiters in self._waiters.items():
                if waiters:
                    waiter_ids.update(waiters)
                future = self._futures.get(hash_key)
                if future and not future.done():
                    future.set_exception(StateError(reason))
                    future.exception()
            waiter_ids.update(self._resolving_waiters)
            waiter_ids.update(self._recovery_waiters)
            self._waiters.clear()
            self._futures.clear()
            self._lead_task_ids.clear()
            self._registered_at.clear()
            self._resolving_waiters.clear()
            self._recovery_waiters.clear()
            self._recovery_attempts.clear()
            self._recovery_available_at.clear()
        return waiter_ids

    async def resolve_future(
        self,
        dedup_hash: str,
        *,
        result: JSONDict | None = None,
        exception: BaseException | None = None,
    ) -> list[str]:
        if not dedup_hash:
            return []
        async with self._lock:
            future = self._futures.get(dedup_hash)
            if not future or future.done():
                return []
            if exception is not None:
                future.set_exception(exception)
                future.exception()
                waiters = self._waiters.pop(dedup_hash, [])
                self._futures.pop(dedup_hash, None)
                self._lead_task_ids.pop(dedup_hash, None)
                self._registered_at.pop(dedup_hash, None)
                resolved_at = time.monotonic()
                self._resolving_waiters.update(
                    {waiter_task_id: resolved_at for waiter_task_id in waiters}
                )
                return waiters
            resolved_result = result if result is not None else {}
            future.set_result(resolved_result)
            waiters = self._waiters.pop(dedup_hash, [])
            self._futures.pop(dedup_hash, None)
            self._lead_task_ids.pop(dedup_hash, None)
            self._registered_at.pop(dedup_hash, None)
            resolved_at = time.monotonic()
            self._resolving_waiters.update(
                {waiter_task_id: resolved_at for waiter_task_id in waiters}
            )
        return waiters

    async def complete_resolution(
        self,
        waiter_ids: list[str],
        unresolved_waiter_ids: list[str],
    ) -> None:
        attempted_waiter_ids = {task_id for task_id in waiter_ids if task_id}
        unresolved = {
            task_id for task_id in unresolved_waiter_ids if task_id in attempted_waiter_ids
        }
        async with self._lock:
            for task_id in attempted_waiter_ids:
                self._resolving_waiters.pop(task_id, None)
                if task_id not in unresolved:
                    self._recovery_waiters.discard(task_id)
                    self._recovery_attempts.pop(task_id, None)
                    self._recovery_available_at.pop(task_id, None)
            current_time = time.monotonic()
            for task_id in unresolved:
                attempt = self._recovery_attempts.get(task_id)
                self._recovery_waiters.add(task_id)
                if attempt is None:
                    self._recovery_attempts[task_id] = 0
                    self._recovery_available_at[task_id] = current_time
                    continue
                delay_seconds = compute_exponential_backoff_seconds(
                    attempt,
                    base_seconds=RECOVERY_RETRY_BASE_SECONDS,
                    maximum_seconds=RECOVERY_RETRY_MAXIMUM_SECONDS,
                    jitter_ratio=RECOVERY_RETRY_JITTER_RATIO,
                )
                self._recovery_attempts[task_id] = attempt + 1
                self._recovery_available_at[task_id] = current_time + delay_seconds

    async def cleanup_expired_entries(self) -> tuple[list[str], str | None]:
        logger = get_logger(LOGGER_NAME)
        current_time = time.monotonic()
        stale_waiter_task_ids: list[str] = []
        stale_reason: str | None = None
        async with self._lock:
            keys_to_cleanup: list[str] = []
            stale_count = 0
            for hash_key, future in list(self._futures.items()):
                registered_at = self._registered_at.get(hash_key, 0.0)
                waiters = self._waiters.get(hash_key, [])
                age_seconds = current_time - registered_at if registered_at else float("inf")
                if future.done() and not waiters:
                    keys_to_cleanup.append(hash_key)
                elif (
                    not future.done()
                    and self._config.waiter_ttl_seconds > 0
                    and age_seconds > self._config.waiter_ttl_seconds
                ):
                    stale_exception = StateError(
                        f"Dedup lead task timed out after {self._config.waiter_ttl_seconds}s",
                    )
                    future.set_exception(stale_exception)
                    future.exception()
                    logger.warning(
                        "Force-resolved stale dedup entry [%s] with %s waiters after TTL expiry.",
                        hash_key[:16],
                        len(waiters),
                    )
                    if waiters:
                        self._recovery_waiters.update(waiters)
                        for task_id in waiters:
                            if task_id not in self._recovery_attempts:
                                self._recovery_attempts[task_id] = 0
                            if task_id not in self._recovery_available_at:
                                self._recovery_available_at[task_id] = current_time
                        stale_reason = str(stale_exception)
                    keys_to_cleanup.append(hash_key)
                    stale_count += 1
            if keys_to_cleanup:
                logger.trace(
                    "Cleaning up %s deduplication entries (%s were stale).",
                    len(keys_to_cleanup),
                    stale_count,
                )
                for key in keys_to_cleanup:
                    self._waiters.pop(key, None)
                    self._futures.pop(key, None)
                    self._lead_task_ids.pop(key, None)
                    self._registered_at.pop(key, None)
            resolution_timeout_seconds = (
                self._config.waiter_ttl_seconds
                if self._config.waiter_ttl_seconds > 0
                else RESOLUTION_OWNERSHIP_TIMEOUT_SECONDS
            )
            stale_resolution_ids = [
                task_id
                for task_id, resolved_at in self._resolving_waiters.items()
                if current_time - resolved_at > resolution_timeout_seconds
            ]
            for task_id in stale_resolution_ids:
                self._resolving_waiters.pop(task_id, None)
                self._recovery_waiters.add(task_id)
                if task_id not in self._recovery_attempts:
                    self._recovery_attempts[task_id] = 0
                if task_id not in self._recovery_available_at:
                    self._recovery_available_at[task_id] = current_time
            available_recovery_ids = [
                task_id
                for task_id in sorted(self._recovery_waiters)
                if self._recovery_available_at.get(task_id, current_time) <= current_time
            ]
            for task_id in available_recovery_ids:
                self._recovery_waiters.discard(task_id)
                self._recovery_available_at.pop(task_id, None)
                self._resolving_waiters[task_id] = current_time
            stale_waiter_task_ids.extend(available_recovery_ids)
            if available_recovery_ids and stale_reason is None:
                stale_reason = "Deduplicated result propagation requires recovery."
        return (stale_waiter_task_ids, stale_reason)
