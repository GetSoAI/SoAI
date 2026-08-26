"""SoAI - Cancellation history tracking and rate limiting [backend/core/tasks/cancellation_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.tasks.cancellation_ids import (
    normalize_cancellation_id,
    require_cancellation_id,
)
from core.tasks.cancellation_types import HistorySnapshot, RecordCancellationResult

__all__ = (
    "CancellationHistory",
    "CancellationHistoryDependencies",
)


@dataclass(frozen=True, slots=True)
class CancellationHistoryDependencies:
    max_history: int = 2048

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CancellationHistoryDependencies",
            max_history=self.max_history,
        )


class CancellationHistory:
    __slots__ = (
        "_cancelled_order",
        "_cancelled_reasons",
        "_in_history_ids",
        "_lock",
        "_publish_timestamps",
        "history_limit",
    )

    def __init__(self, deps: CancellationHistoryDependencies) -> None:
        self._cancelled_reasons: dict[str, str] = {}
        self._cancelled_order: deque[str] = deque()
        self._in_history_ids: set[str] = set()
        self._publish_timestamps: dict[str, float] = {}
        self.history_limit = max(1, int(deps.max_history))
        self._lock = asyncio.Lock()

    async def record_cancellation(
        self,
        cancellation_id: str,
        reason: str,
        *,
        active_scopes: set[str] | None = None,
    ) -> RecordCancellationResult:
        normalized_id = require_cancellation_id(cancellation_id)
        normalized_reason = str(reason or "").strip() or "Cancelled"
        async with self._lock:
            if normalized_id in self._cancelled_reasons:
                existing_reason = self._cancelled_reasons.get(normalized_id, normalized_reason)
                return RecordCancellationResult(
                    recorded=False,
                    reason=existing_reason,
                )
            self._cancelled_reasons[normalized_id] = normalized_reason
            self._cancelled_order.append(normalized_id)
            self._in_history_ids.add(normalized_id)
            self._trim_history_locked(active_scopes or set())
        return RecordCancellationResult(
            recorded=True,
            reason=normalized_reason,
        )

    async def is_cancelled(self, cancellation_id: str) -> bool:
        normalized_id = normalize_cancellation_id(cancellation_id)
        if not normalized_id:
            return False
        async with self._lock:
            return self._find_reason_for_scope_locked(normalized_id) is not None

    async def get_reason(self, cancellation_id: str) -> str | None:
        normalized_id = normalize_cancellation_id(cancellation_id)
        if not normalized_id:
            return None
        async with self._lock:
            return self._find_reason_for_scope_locked(normalized_id)

    async def check_publish_rate_limit(self, cancellation_id: str, *, min_interval: float) -> bool:
        normalized_id = normalize_cancellation_id(cancellation_id)
        if not normalized_id:
            return False
        min_interval_value = max(0.0, float(min_interval))
        now = time.monotonic()
        async with self._lock:
            last_published = self._publish_timestamps.get(normalized_id)
            if last_published is not None and (now - last_published) < min_interval_value:
                return False
            self._publish_timestamps[normalized_id] = now
            if len(self._publish_timestamps) > (self.history_limit * 4):
                self._cleanup_stale_publish_timestamps_locked()
        return True

    async def clear_scope(self, cancellation_id: str) -> bool:
        normalized_id = require_cancellation_id(cancellation_id)
        removed = False
        async with self._lock:
            if self._cancelled_reasons.pop(normalized_id, None) is not None:
                removed = True
            if normalized_id in self._in_history_ids:
                self._in_history_ids.discard(normalized_id)
                removed = True
            if normalized_id in self._cancelled_order:
                self._cancelled_order.remove(normalized_id)
                removed = True
            if self._publish_timestamps.pop(normalized_id, None) is not None:
                removed = True
        return removed

    async def clear_all(self) -> None:
        async with self._lock:
            self._cancelled_reasons.clear()
            self._cancelled_order.clear()
            self._in_history_ids.clear()
            self._publish_timestamps.clear()

    async def get_snapshot(self) -> HistorySnapshot:
        async with self._lock:
            return HistorySnapshot(
                cancelled_reasons=self._cancelled_reasons.copy(),
                cancelled_order=list(self._cancelled_order),
                max_history=self.history_limit,
            )

    async def update_limit(
        self,
        max_history: int,
        *,
        active_scopes: set[str] | None = None,
    ) -> None:
        updated_limit = max(1, int(max_history))
        async with self._lock:
            self.history_limit = updated_limit
            self._trim_history_locked(active_scopes or set())

    async def has_entries(self) -> bool:
        async with self._lock:
            return bool(
                self._cancelled_reasons or self._cancelled_order or self._publish_timestamps,
            )

    def _trim_history_locked(self, active_scopes: set[str]) -> tuple[str, ...]:
        trimmed: list[str] = []
        while len(self._cancelled_order) > self.history_limit:
            oldest = self._cancelled_order.popleft()
            self._in_history_ids.discard(oldest)
            if oldest not in active_scopes:
                self._cancelled_reasons.pop(oldest, None)
            self._publish_timestamps.pop(oldest, None)
            trimmed.append(oldest)
        return tuple(trimmed)

    def _cleanup_stale_publish_timestamps_locked(self) -> None:
        stale_entries = list(self._publish_timestamps.items())
        stale_entries.sort(key=lambda entry: entry[1])
        for cancellation_key, _ in stale_entries[: len(stale_entries) // 2]:
            self._publish_timestamps.pop(cancellation_key, None)

    def _find_reason_for_scope_locked(self, normalized_id: str) -> str | None:
        direct_reason = self._cancelled_reasons.get(normalized_id)
        if direct_reason is not None:
            return direct_reason
        prefix = normalized_id
        while True:
            separator_index = prefix.rfind("::")
            if separator_index < 0:
                return None
            prefix = prefix[:separator_index]
            inherited_reason = self._cancelled_reasons.get(prefix)
            if inherited_reason is not None:
                return inherited_reason
