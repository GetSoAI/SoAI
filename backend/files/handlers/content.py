"""SoAI - File content query handler [backend/files/handlers/content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_files import FileContentQuery
from core.files.protocols import DatabaseFilesProtocol
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from files.command_execution import execute_or_error
from files.streaming import stream_file_content

__all__ = ("handle_file_content",)


async def handle_file_content(
    command: FileContentQuery,
    *,
    storage_root: str,
    database_files: DatabaseFilesProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    task_registry: TaskRegistryProtocol,
    shutdown_event: asyncio.Event,
) -> None:
    async def _action() -> None:
        await stream_file_content(
            command,
            storage_root=storage_root,
            database_files=database_files,
            cancellation_binder=cancellation_binder,
            task_registry=task_registry,
            shutdown_event=shutdown_event,
        )

    await execute_or_error(
        command.reply_channel,
        f"File content streaming for '{command.payload.get('file_id')}' failed",
        _action,
        task_registry=task_registry,
    )
