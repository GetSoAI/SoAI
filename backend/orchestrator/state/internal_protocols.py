"""SoAI - Internal protocols for orchestrator state helpers [backend/orchestrator/state/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

from core.concurrency.protocols import AsyncContextManagerProtocol
from core.logging.protocols import TraceLogger
from core.state.protocols import ImmutablePluginStates
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.events.types_plugins import (
        PluginInstallationStateChangedEvent,
        PluginRuntimeStateChangedEvent,
    )
    from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
    from core.state.health_status import PluginHealthStatus
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "MainStateControllerProtocol",
    "PluginStateLockRegistryProtocol",
    "PluginStateStoreProtocol",
    "PluginStateStoreQueryProtocol",
)


class PluginStateLockRegistryProtocol(Protocol):
    def lock(self, key: str) -> AsyncContextManagerProtocol[None]: ...


class PluginStateStoreQueryProtocol(Protocol):
    global_lock: asyncio.Lock
    plugin_locks: PluginStateLockRegistryProtocol
    plugin_states: dict[str, JSONDict]
    immutable_snapshot_cache: ImmutablePluginStates | None
    state_version: int
    logger: TraceLogger

    def invalidate_snapshot_cache(self) -> None: ...


class PluginStateStoreProtocol(Protocol):
    state_version: int

    async def bootstrap_from_database(self) -> None: ...

    async def apply_state_change(
        self,
        event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
    ) -> bool: ...

    async def apply_purge(self, plugin_name: str) -> bool: ...

    async def clear_purged_status(self, plugin_name: str) -> None: ...

    async def get_state_version(self) -> int: ...

    async def get_all_states(self) -> ImmutablePluginStates: ...

    async def get_all_states_with_version(self) -> tuple[ImmutablePluginStates, int]: ...

    async def get_status(self, plugin_name: str) -> PluginRuntimeStateName: ...

    async def update_health_status(
        self,
        plugin_name: str,
        health_status: PluginHealthStatus,
    ) -> None: ...

    async def get_health_statuses(self) -> dict[str, PluginHealthStatus]: ...


class MainStateControllerProtocol(Protocol):
    async def recalculate_state(
        self,
        all_plugin_states: ImmutablePluginStates,
        reason: str,
    ) -> SoAIMainState | None: ...

    async def apply_override(
        self,
        event: SystemMainStateOverrideEvent,
        on_expiry_recalculate: Callable[[], Awaitable[None]],
    ) -> None: ...

    async def shutdown(self) -> None: ...

    async def set_state(self, new_state: SoAIMainState, reason: str) -> None: ...

    async def get_state(self) -> dict[str, str]: ...
