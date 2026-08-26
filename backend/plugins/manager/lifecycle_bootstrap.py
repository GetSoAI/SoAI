"""SoAI - Plugin manager bootstrap helpers [backend/plugins/manager/lifecycle_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.events.subscriptions import subscribe_many
from core.events.types_base import Event
from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = ("register_plugin_manager_subscriptions",)


def register_plugin_manager_subscriptions(
    manager: PluginManagerLifecycleTarget,
    command_map: dict[type[Event], Callable[[Event], Awaitable[None]]],
) -> None:
    subscribe_many(manager.dependencies.infrastructure.event_bus, command_map)
