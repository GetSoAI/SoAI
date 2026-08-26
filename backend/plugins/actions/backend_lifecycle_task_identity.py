"""SoAI - Plugin backend lifecycle task identity resolution [backend/plugins/actions/backend_lifecycle_task_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("resolve_lifecycle_task_id",)


def resolve_lifecycle_task_id(
    command: InstallPluginBackendCommand | UpdatePluginBackendCommand | RemovePluginBackendCommand,
    task_registry: TaskRegistryProtocol,
    task_id: str | None,
) -> str | None:
    if task_id is not None:
        return task_id
    if command.reply_channel is None:
        return None
    identity = task_registry.resolve_task_identity_for_reply_queue(command.reply_channel)
    if identity is None:
        return None
    return identity[0]
