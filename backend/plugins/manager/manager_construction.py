"""SoAI - PluginManager core properties and helpers [backend/plugins/manager/manager_construction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.network_policy import require_online_mode
from plugins.manager.capability_support import require_supported_plugin_capability

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "bind_orchestrator_lifecycle",
    "require_plugin_capability",
    "require_plugin_manager_online_mode",
    "resolve_downloads_enabled",
    "resolve_uploads_enabled",
)


def bind_orchestrator_lifecycle(
    plugin_manager: PluginManagerRuntimeProtocol,
    orchestrator_lifecycle: OrchestratorLifecycleProtocol,
) -> None:
    plugin_manager.orchestrator_lifecycle = orchestrator_lifecycle


def require_plugin_manager_online_mode(
    plugin_manager: PluginManagerRuntimeProtocol,
    source: str,
) -> None:
    require_online_mode(
        plugin_manager.dependencies.infrastructure.runtime_flags,
        source=f"plugin_manager:{source}",
    )


def resolve_uploads_enabled(plugin_manager: PluginManagerRuntimeProtocol) -> bool:
    return bool(plugin_manager.state.configuration.uploads_enabled)


def resolve_downloads_enabled(plugin_manager: PluginManagerRuntimeProtocol) -> bool:
    return bool(plugin_manager.state.configuration.downloads_enabled)


def require_plugin_capability(
    _plugin_manager: PluginManagerRuntimeProtocol,
    instance: PluginInstanceProtocol,
    capability_name: str,
    failure_message: str,
) -> None:
    require_supported_plugin_capability(instance, capability_name, failure_message)
