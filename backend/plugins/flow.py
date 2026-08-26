"""SoAI - Plugin manager command routing [backend/plugins/flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable

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
from core.plugins.protocols_lifecycle import SchedulableCommandProtocol
from plugins.actions.backend_bulk_update import process_update_all_backends_async
from plugins.actions.backend_lifecycle_commands import (
    process_install_command_async,
    process_remove_command_async,
    process_update_command_async,
)
from plugins.actions.model_download import process_model_download_async
from plugins.actions.plugin_package_download import (
    process_plugin_package_download_async,
)
from plugins.actions.upload import process_upload_plugin_async
from plugins.clone.command_handler import process_clone_command_async
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.registry.delete import process_delete_plugin_async
from plugins.registry.force_cleanup import process_force_cleanup_plugin_async

__all__ = ()


def _schedule_command_task(
    self: PluginManagerRuntimeProtocol,
    command: SchedulableCommandProtocol,
    *,
    command_coro: Awaitable[None],
    name_template: str,
) -> None:
    self.dependencies.infrastructure.lifecycle.schedule_command_task(
        service_name="Plugin manager",
        command=command,
        coro=command_coro,
        name_template=name_template,
    )


async def handle_install_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, InstallPluginBackendCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_install_command_async(self, event),
        name_template="plugin-install-{plugin_name}",
    )


async def handle_update_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, UpdatePluginBackendCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_update_command_async(self, event),
        name_template="plugin-update-{plugin_name}",
    )


async def handle_remove_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, RemovePluginBackendCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_remove_command_async(self, event),
        name_template="plugin-remove-{plugin_name}",
    )


async def handle_update_all_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, UpdateAllPluginBackendsCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_update_all_backends_async(self, event),
        name_template="plugin-update-all",
    )


async def handle_download_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, ModelDownloadCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_model_download_async(self, event),
        name_template="plugin-download-{plugin_name}",
    )


async def handle_upload_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, UploadPluginCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_upload_plugin_async(self, event),
        name_template="plugin-upload",
    )


async def handle_plugin_package_download_command(
    self: PluginManagerRuntimeProtocol,
    event: Event,
) -> None:
    if not isinstance(event, DownloadPluginPackageCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_plugin_package_download_async(self, event),
        name_template="plugin-package-download",
    )


async def handle_delete_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, DeletePluginCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_delete_plugin_async(self, event),
        name_template="plugin-delete-{plugin_name}",
    )


async def handle_force_cleanup_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, ForceCleanupPluginCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_force_cleanup_plugin_async(self, event),
        name_template="plugin-force-cleanup-{plugin_name}",
    )


async def handle_clone_command(self: PluginManagerRuntimeProtocol, event: Event) -> None:
    if not isinstance(event, ClonePluginCommand):
        return
    _schedule_command_task(
        self,
        event,
        command_coro=process_clone_command_async(self, event),
        name_template="plugin-clone-{plugin_name}",
    )
