"""SoAI - GDELT DOC provider access control [backend/mcp/tools/news_provider_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.errors.exceptions import RateLimitError, StateError
from core.logging.rate_limited_logger import RateLimitedLogger
from core.state.circuit_breaker import CircuitBreaker, CircuitBreakerState
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    parse_retry_after_seconds,
)

__all__ = ("NewsProviderAccessController",)

_DEFAULT_MIN_INTERVAL_SECONDS = 12.0
_QUERY_STATE_TTL_SECONDS = 1800.0
_DISTINCT_QUERY_WINDOW_SECONDS = 300.0
_INITIAL_COOLDOWN_SECONDS = 300.0
_MAXIMUM_COOLDOWN_SECONDS = 1800.0


@dataclass(frozen=True, slots=True)
class _QueryCooldown:
    failure_count: int
    blocked_until_monotonic: float


def _new_query_cooldowns() -> TTLCache[str, _QueryCooldown]:
    return TTLCache(
        TTLCacheDependencies(
            ttl_seconds=_QUERY_STATE_TTL_SECONDS,
            max_size=256,
        ),
    )


def _new_distinct_queries() -> TTLCache[str, bool]:
    return TTLCache(
        TTLCacheDependencies(
            ttl_seconds=_DISTINCT_QUERY_WINDOW_SECONDS,
            max_size=256,
        ),
    )


def _new_circuit_breaker() -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout_sec=_DISTINCT_QUERY_WINDOW_SECONDS,
        failure_window_sec=_DISTINCT_QUERY_WINDOW_SECONDS,
    )


@dataclass(slots=True)
class NewsProviderAccessController:
    min_interval_seconds: float = _DEFAULT_MIN_INTERVAL_SECONDS
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_allowed_monotonic: float = field(default=0.0, init=False)
    query_cooldowns: TTLCache[str, _QueryCooldown] = field(
        default_factory=_new_query_cooldowns,
    )
    distinct_rate_limited_queries: TTLCache[str, bool] = field(
        default_factory=_new_distinct_queries,
    )
    circuit_breaker: CircuitBreaker = field(default_factory=_new_circuit_breaker)
    fallback_failure_limiter: RateLimitedLogger = field(
        default_factory=lambda: RateLimitedLogger(interval_seconds=300.0),
    )
    active_query_key: str | None = field(default=None, init=False)
    active_outcome_recorded: bool = field(default=False, init=False)

    def _require_active_query(self, query_key: str) -> None:
        if self.active_query_key != query_key or not self.lock.locked():
            raise StateError("News provider outcome recorded outside its request slot.")

    def _raise_if_query_blocked(self, query_key: str, now_monotonic: float) -> None:
        cooldown = self.query_cooldowns.get(query_key)
        if cooldown is None:
            return
        if now_monotonic >= cooldown.blocked_until_monotonic:
            return
        raise RateLimitError("News provider rate limit cooldown is active.")

    def _raise_if_circuit_blocked(self) -> None:
        if not self.circuit_breaker.allow_request():
            raise RateLimitError("News provider rate limit circuit is open.")

    async def _wait_for_interval(self, now_monotonic: float) -> None:
        wait_seconds = self.next_allowed_monotonic - now_monotonic
        if wait_seconds > 0.0:
            await asyncio.sleep(wait_seconds)
        started_monotonic = time.monotonic()
        self.next_allowed_monotonic = started_monotonic + max(
            0.0,
            self.min_interval_seconds,
        )

    @asynccontextmanager
    async def request_slot(self, query_key: str) -> AsyncGenerator[None]:
        async with self.lock:
            now_monotonic = time.monotonic()
            self._raise_if_query_blocked(query_key, now_monotonic)
            self._raise_if_circuit_blocked()
            try:
                await self._wait_for_interval(now_monotonic)
            except asyncio.CancelledError:
                self.circuit_breaker.release_half_open_probe()
                raise
            self.active_query_key = query_key
            self.active_outcome_recorded = False
            try:
                yield
            finally:
                if not self.active_outcome_recorded:
                    self.circuit_breaker.release_half_open_probe()
                self.active_query_key = None
                self.active_outcome_recorded = False

    def record_success(self, query_key: str) -> None:
        self._require_active_query(query_key)
        self.active_outcome_recorded = True
        self.query_cooldowns.delete(query_key)
        if self.circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
            self.distinct_rate_limited_queries.clear()
            self.circuit_breaker.record_success()

    def record_rate_limit(self, query_key: str, retry_after: str | None) -> None:
        self._require_active_query(query_key)
        self.active_outcome_recorded = True
        previous = self.query_cooldowns.get(query_key)
        failure_count = 1 if previous is None else previous.failure_count + 1
        calculated_seconds = compute_exponential_backoff_seconds(
            failure_count - 1,
            base_seconds=_INITIAL_COOLDOWN_SECONDS,
            maximum_seconds=_MAXIMUM_COOLDOWN_SECONDS,
        )
        retry_after_seconds = float(
            parse_retry_after_seconds(retry_after, default_seconds=0),
        )
        cooldown_seconds = min(
            _MAXIMUM_COOLDOWN_SECONDS,
            max(calculated_seconds, retry_after_seconds),
        )
        self.query_cooldowns.put(
            query_key,
            _QueryCooldown(
                failure_count=failure_count,
                blocked_until_monotonic=time.monotonic() + cooldown_seconds,
            ),
        )
        if self.distinct_rate_limited_queries.get(query_key) is None:
            self.distinct_rate_limited_queries.put(query_key, True)
            self.circuit_breaker.record_failure()

    def record_transient_failure(self, query_key: str) -> None:
        self._require_active_query(query_key)
        self.active_outcome_recorded = True
        if self.circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
            self.circuit_breaker.record_failure()
