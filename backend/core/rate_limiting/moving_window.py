"""SoAI - Core moving-window rate limiter [backend/core/rate_limiting/moving_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time
from collections import deque
from math import ceil

from core.rate_limiting.definitions import (
    RateLimitDecision,
    RateLimitRule,
    RateLimitWindowStats,
)
from core.timing.epoch import epoch_seconds_float

__all__ = ("MovingWindowRateLimiter",)

SWEEP_INTERVAL_SECONDS = 60.0


class MovingWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str, str], deque[float]] = {}
        self._window_seconds_by_key: dict[tuple[str, str, str], int] = {}
        self._last_sweep_monotonic = 0.0

    def hit(
        self,
        *,
        rules: tuple[RateLimitRule, ...],
        client_key: str,
        scope_key: str,
    ) -> RateLimitDecision:
        now_monotonic = time.monotonic()
        now_epoch = epoch_seconds_float()
        with self._lock:
            self._sweep_expired_buckets(now_monotonic)
            failed_rule: RateLimitRule | None = None
            failed_stats: RateLimitWindowStats | None = None
            writable_buckets: dict[tuple[str, str, str], deque[float]] = {}
            for rule in rules:
                bucket_key = self._build_bucket_key(rule, client_key, scope_key)
                if bucket_key in writable_buckets:
                    continue
                bucket = self._resolve_bucket(bucket_key, rule.window_seconds)
                self._prune(bucket, rule, now_monotonic)
                if len(bucket) >= rule.amount:
                    failed_rule = rule
                    failed_stats = self._build_stats(rule, bucket, now_monotonic, now_epoch)
                    break
                writable_buckets[bucket_key] = bucket
            if failed_rule is not None:
                return RateLimitDecision(
                    allowed=False,
                    failed_rule=failed_rule,
                    stats=failed_stats,
                )
            for bucket in writable_buckets.values():
                bucket.append(now_monotonic)
            return RateLimitDecision(allowed=True, failed_rule=None, stats=None)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._window_seconds_by_key.clear()
            self._last_sweep_monotonic = 0.0

    def _build_bucket_key(
        self,
        rule: RateLimitRule,
        client_key: str,
        scope_key: str,
    ) -> tuple[str, str, str]:
        return (client_key, scope_key, rule.storage_key)

    def _resolve_bucket(self, key: tuple[str, str, str], window_seconds: int) -> deque[float]:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = deque[float]()
            self._buckets[key] = bucket
            self._window_seconds_by_key[key] = window_seconds
        return bucket

    def _prune(
        self,
        bucket: deque[float],
        rule: RateLimitRule,
        now_monotonic: float,
    ) -> None:
        threshold = now_monotonic - float(rule.window_seconds)
        while bucket and bucket[0] <= threshold:
            bucket.popleft()

    def _sweep_expired_buckets(self, now_monotonic: float) -> None:
        if now_monotonic - self._last_sweep_monotonic < SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep_monotonic = now_monotonic
        expired_keys: list[tuple[str, str, str]] = []
        for bucket_key, bucket in self._buckets.items():
            window_seconds = self._window_seconds_by_key[bucket_key]
            threshold = now_monotonic - float(window_seconds)
            while bucket and bucket[0] <= threshold:
                bucket.popleft()
            if not bucket:
                expired_keys.append(bucket_key)
        for bucket_key in expired_keys:
            del self._buckets[bucket_key]
            del self._window_seconds_by_key[bucket_key]

    def _build_stats(
        self,
        rule: RateLimitRule,
        bucket: deque[float],
        now_monotonic: float,
        now_epoch: float,
    ) -> RateLimitWindowStats:
        oldest = bucket[0] if bucket else now_monotonic
        reset_delta = max(0.0, oldest + float(rule.window_seconds) - now_monotonic)
        reset_epoch_seconds = int(ceil(now_epoch + reset_delta))
        remaining = max(0, int(rule.amount) - len(bucket))
        return RateLimitWindowStats(
            limit=rule.amount,
            remaining=remaining,
            reset_epoch_seconds=reset_epoch_seconds,
        )
