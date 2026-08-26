"""SoAI - Plugin capability enforcement [backend/plugins/manager/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.errors import PluginCapabilityError
from plugins.manager.capability_support import (
    supports_plugin_capability_from_instance,
    supports_plugin_capability_from_record,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("ensure_plugin_capability",)


async def ensure_plugin_capability(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    capability_name: str,
    action_description: str,
) -> None:
    await manager.require_ready()
    instance = await manager.get_plugin_instance(plugin_name)
    supports_capability = False
    if instance is not None:
        supports_capability = supports_plugin_capability_from_instance(
            instance,
            capability_name,
        )
    else:
        plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        if plugin_record is not None:
            supports_capability = supports_plugin_capability_from_record(
                plugin_record,
                capability_name,
            )
    if not supports_capability:
        display_name = await manager.get_plugin_display_name(plugin_name)
        raise PluginCapabilityError(
            plugin_name,
            capability_name,
            f"Action '{action_description}' is not supported by plugin '{display_name}'.",
        )
