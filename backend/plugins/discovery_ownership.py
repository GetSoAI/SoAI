"""SoAI - Plugin discovery lock ownership and control supersession [backend/plugins/discovery_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum

from core.di.validation import require_dependencies
from core.plugins.protocols_lifecycle import PluginLifecycleLocksProtocol
from core.types.json import JSONDict

__all__ = (
    "PluginDiscoveryOperation",
    "PluginDiscoveryOwnership",
    "PluginDiscoveryOwnershipDependencies",
    "PluginDiscoveryPhase",
)


class PluginDiscoveryPhase(StrEnum):
    PRECHECK = "precheck"
    PROVIDER = "provider"
    AWAITING_RECONCILIATION = "awaiting_reconciliation"
    RECONCILING = "reconciling"
    SUPERSEDED = "superseded"


class PluginDiscoveryOperation:
    __slots__ = ("_cancel_provider", "_cleanup_failed", "_phase", "_release", "completed")

    def __init__(self) -> None:
        loop = asyncio.get_running_loop()
        self._phase = PluginDiscoveryPhase.PRECHECK
        self._cancel_provider: Callable[[], bool] | None = None
        self._cleanup_failed = False
        self._release: asyncio.Future[None] = loop.create_future()
        self.completed: asyncio.Future[None] = loop.create_future()

    @property
    def phase(self) -> PluginDiscoveryPhase:
        return self._phase

    @property
    def superseded(self) -> bool:
        return self._phase is PluginDiscoveryPhase.SUPERSEDED

    @property
    def cleanup_failed(self) -> bool:
        return self._cleanup_failed

    def begin_provider_phase(self, cancel_provider: Callable[[], bool]) -> bool:
        if self.superseded:
            return False
        self._phase = PluginDiscoveryPhase.PROVIDER
        self._cancel_provider = cancel_provider
        return True

    async def await_reconciliation(self) -> None:
        if self.superseded:
            return
        self._phase = PluginDiscoveryPhase.AWAITING_RECONCILIATION
        await asyncio.shield(self._release)

    def freeze(self) -> bool:
        if self.superseded:
            return False
        self._phase = PluginDiscoveryPhase.RECONCILING
        return True

    def settle(self) -> None:
        if not self._release.done():
            self._release.set_result(None)

    def record_cleanup_failure(self) -> None:
        self._cleanup_failed = True

    def supersede(self) -> None:
        previous_phase = self._phase
        if previous_phase in {PluginDiscoveryPhase.RECONCILING, PluginDiscoveryPhase.SUPERSEDED}:
            return
        self._phase = PluginDiscoveryPhase.SUPERSEDED
        if previous_phase is PluginDiscoveryPhase.PROVIDER and self._cancel_provider is not None:
            self._cancel_provider()
        self.settle()


@dataclass(frozen=True, slots=True)
class PluginDiscoveryOwnershipDependencies:
    locks: PluginLifecycleLocksProtocol

    def __post_init__(self) -> None:
        require_dependencies(owner="PluginDiscoveryOwnershipDependencies", locks=self.locks)


class PluginDiscoveryOwnership:
    def __init__(self, deps: PluginDiscoveryOwnershipDependencies) -> None:
        self._deps = deps
        self._operations: dict[str, PluginDiscoveryOperation] = {}
        self._control_reservations: dict[str, int] = {}

    def is_plugin_locked_by_discovery(self, plugin_name: str) -> bool:
        return plugin_name in self._operations

    def describe_ownership(self, plugin_name: str) -> JSONDict:
        operation = self._operations.get(plugin_name)
        return {
            "discovery_phase": operation.phase.value if operation is not None else None,
            "discovery_cleanup_failed": operation is not None and operation.cleanup_failed,
            "control_reservations": self._control_reservations.get(plugin_name, 0),
        }

    @asynccontextmanager
    async def discovery_scope(
        self,
        plugin_name: str,
        *,
        timeout_seconds: float | None,
    ) -> AsyncGenerator[PluginDiscoveryOperation | None]:
        operation: PluginDiscoveryOperation | None = None
        if plugin_name in self._control_reservations:
            yield None
            return
        try:
            async with AsyncExitStack() as lock_stack:
                if timeout_seconds is None:
                    await lock_stack.enter_async_context(self._deps.locks[plugin_name])
                    lock_acquired = True
                else:
                    lock_result = await lock_stack.enter_async_context(
                        self._deps.locks.bounded_lock(plugin_name, timeout_seconds),
                    )
                    lock_acquired = lock_result.acquired
                if lock_acquired and plugin_name not in self._control_reservations:
                    operation = PluginDiscoveryOperation()
                    self._operations[plugin_name] = operation
                try:
                    yield operation
                finally:
                    if operation is not None:
                        self._operations.pop(plugin_name, None)
        finally:
            if operation is not None and not operation.completed.done():
                operation.completed.set_result(None)

    @asynccontextmanager
    async def control_scope(
        self,
        plugin_name: str,
        *,
        timeout_seconds: float,
    ) -> AsyncGenerator[bool]:
        self._control_reservations[plugin_name] = self._control_reservations.get(plugin_name, 0) + 1
        try:
            yield await self._drain_discovery(plugin_name, timeout_seconds)
        finally:
            remaining_reservations = self._control_reservations[plugin_name] - 1
            if remaining_reservations:
                self._control_reservations[plugin_name] = remaining_reservations
            else:
                del self._control_reservations[plugin_name]

    async def _drain_discovery(self, plugin_name: str, timeout_seconds: float) -> bool:
        operation = self._operations.get(plugin_name)
        if operation is None:
            return True
        operation.supersede()
        try:
            async with asyncio.timeout(timeout_seconds):
                await asyncio.shield(operation.completed)
        except TimeoutError:
            return False
        return not operation.cleanup_failed
