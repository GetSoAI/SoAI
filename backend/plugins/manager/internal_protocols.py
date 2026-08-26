"""SoAI - Internal protocol contracts for plugin manager lifecycle [backend/plugins/manager/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "PluginManagerLifecycleSubscriptionsProtocol",
    "PluginManagerLifecycleTarget",
)


class PluginManagerLifecycleTarget(PluginManagerRuntimeProtocol, Protocol):
    async def begin_shutdown(self) -> None: ...

    async def finalize_shutdown(self) -> None: ...

    async def shutdown(self) -> None: ...


class PluginManagerLifecycleSubscriptionsProtocol(Protocol):
    @property
    def subscriptions_registered(self) -> bool: ...

    @subscriptions_registered.setter
    def subscriptions_registered(self, value: bool) -> None: ...
