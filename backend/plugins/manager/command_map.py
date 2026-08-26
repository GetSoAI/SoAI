"""SoAI - Plugin manager command subscription map construction [backend/plugins/manager/command_map.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable

from core.events.types_base import Event
from core.events.types_models_model_commands import ModelDownloadCommand
from core.events.types_plugins import (
    ClonePluginCommand,
    DeletePluginCommand,
    DownloadPluginPackageCommand,
    ForceCleanupPluginCommand,
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdateAllPluginBackendsCommand,
    UpdatePluginBackendCommand,
    UploadPluginCommand,
)
from core.events.types_tasks import CancelTaskCommand
from plugins.flow import (
    handle_clone_command,
    handle_delete_command,
    handle_download_command,
    handle_force_cleanup_command,
    handle_install_command,
    handle_plugin_package_download_command,
    handle_remove_command,
    handle_update_all_command,
    handle_update_command,
    handle_upload_command,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("build_plugin_command_map",)


def build_plugin_command_map(
    manager: PluginManagerRuntimeProtocol,
) -> dict[type[Event], Callable[[Event], Awaitable[None]]]:
    plugin_flow_handlers: dict[
        type[Event],
        Callable[[PluginManagerRuntimeProtocol, Event], Awaitable[None]],
    ] = {
        InstallPluginBackendCommand: handle_install_command,
        UpdatePluginBackendCommand: handle_update_command,
        RemovePluginBackendCommand: handle_remove_command,
        UpdateAllPluginBackendsCommand: handle_update_all_command,
        ModelDownloadCommand: handle_download_command,
        DownloadPluginPackageCommand: handle_plugin_package_download_command,
        UploadPluginCommand: handle_upload_command,
        DeletePluginCommand: handle_delete_command,
        ForceCleanupPluginCommand: handle_force_cleanup_command,
        ClonePluginCommand: handle_clone_command,
    }
    command_map: dict[type[Event], Callable[[Event], Awaitable[None]]] = {
        event_class: functools.partial(handler, manager)
        for event_class, handler in plugin_flow_handlers.items()
    }
    command_map[CancelTaskCommand] = manager.handle_cancel_task
    return command_map
