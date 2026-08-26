"""SoAI - Scheduler plugin purge state [backend/orchestrator/scheduling/purge_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

__all__ = (
    "PurgeStateSnapshot",
    "SchedulerPurgeState",
)


@dataclass(frozen=True, slots=True)
class PurgeStateSnapshot:
    is_purging: bool
    reason: str
    allow_failover: bool


@dataclass(slots=True)
class _NestedPurgeScope:
    default_reason: str
    allow_failover: bool
    depth: int = 0
    reason: str | None = None

    def begin(self, *, reason: str) -> None:
        self.depth += 1
        self.reason = str(reason or "").strip() or self.default_reason

    def finish(self) -> bool:
        if self.depth <= 1:
            self.depth = 0
            self.reason = None
            return False
        self.depth -= 1
        return True

    def snapshot(self) -> PurgeStateSnapshot | None:
        if self.depth <= 0:
            return None
        return PurgeStateSnapshot(
            is_purging=True,
            reason=self.reason or self.default_reason,
            allow_failover=self.allow_failover,
        )


class SchedulerPurgeState:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._global_purge = _NestedPurgeScope(
            default_reason="Plugin queues are being purged.",
            allow_failover=False,
        )
        self._plugin_purges: dict[str, _NestedPurgeScope] = {}
        self._active_admissions = 0
        self._active_plugin_admissions: dict[str, int] = {}

    def _snapshot_locked(self, plugin_name: str) -> PurgeStateSnapshot:
        global_snapshot = self._global_purge.snapshot()
        if global_snapshot is not None:
            return global_snapshot
        plugin_scope = self._plugin_purges.get(plugin_name)
        plugin_snapshot = plugin_scope.snapshot() if plugin_scope is not None else None
        if plugin_snapshot is not None:
            return plugin_snapshot
        return PurgeStateSnapshot(is_purging=False, reason="", allow_failover=True)

    async def snapshot(self, plugin_name: str) -> PurgeStateSnapshot:
        async with self._condition:
            return self._snapshot_locked(plugin_name)

    async def begin_global_purge(self, *, reason: str) -> None:
        async with self._condition:
            self._global_purge.begin(reason=reason)
            self._condition.notify_all()
            await self._condition.wait_for(self._global_admissions_drained)

    async def finish_global_purge(self) -> None:
        async with self._condition:
            self._global_purge.finish()
            self._condition.notify_all()

    async def begin_plugin_purge(self, plugin_name: str, *, reason: str) -> None:
        if not plugin_name:
            return
        async with self._condition:
            plugin_scope = self._plugin_purges.get(plugin_name)
            if plugin_scope is None:
                plugin_scope = _NestedPurgeScope(
                    default_reason=f"Plugin queue for '{plugin_name}' is being purged.",
                    allow_failover=True,
                )
                self._plugin_purges[plugin_name] = plugin_scope
            plugin_scope.begin(reason=reason)
            self._condition.notify_all()
            await self._condition.wait_for(
                lambda: self._plugin_admissions_drained(plugin_name),
            )

    async def finish_plugin_purge(self, plugin_name: str) -> None:
        if not plugin_name:
            return
        async with self._condition:
            plugin_scope = self._plugin_purges.get(plugin_name)
            if plugin_scope is None:
                return
            still_active = plugin_scope.finish()
            if not still_active:
                self._plugin_purges.pop(plugin_name, None)
            self._condition.notify_all()

    async def run_when_not_purging(
        self,
        plugin_name: str,
        action: Callable[[], Awaitable[None]],
    ) -> PurgeStateSnapshot:
        async with self._condition:
            snapshot = self._snapshot_locked(plugin_name)
            if snapshot.is_purging:
                return snapshot
            self._active_admissions += 1
            self._active_plugin_admissions[plugin_name] = (
                self._active_plugin_admissions.get(plugin_name, 0) + 1
            )
        try:
            await action()
        finally:
            async with self._condition:
                self._active_admissions -= 1
                plugin_admissions = self._active_plugin_admissions.get(plugin_name, 0) - 1
                if plugin_admissions > 0:
                    self._active_plugin_admissions[plugin_name] = plugin_admissions
                else:
                    self._active_plugin_admissions.pop(plugin_name, None)
                self._condition.notify_all()
        return snapshot

    def _global_admissions_drained(self) -> bool:
        return self._active_admissions <= 0

    def _plugin_admissions_drained(self, plugin_name: str) -> bool:
        return self._active_plugin_admissions.get(plugin_name, 0) <= 0
