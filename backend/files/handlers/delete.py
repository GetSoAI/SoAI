"""SoAI - File delete command handler [backend/files/handlers/delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.events.types_files import FileDeleteCommand
from core.events.types_models_streaming import InferenceResultEvent
from core.files.managed_file_deletion import delete_managed_file
from core.files.managed_storage_errors import FileDeletionSecurityError
from core.files.protocols import DatabaseFilesProtocol
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from files.command_execution import execute_or_error
from files.handlers.response import deliver_reply_event_or_raise
from files.lookup import get_file_info_or_fail

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_file_delete",)

LOGGER_NAME = "SoAI.files.handlers.delete"
OPERATION = "files.handlers.delete.handle_file_delete"


async def handle_file_delete(
    command: FileDeleteCommand,
    *,
    storage_root: str,
    database_files: DatabaseFilesProtocol,
    task_registry: TaskRegistryProtocol,
) -> None:
    async def _action() -> None:
        logger = get_logger(LOGGER_NAME)
        file_info = await get_file_info_or_fail(
            database_files,
            command.file_id,
            with_path=True,
            enforce_owner=True,
            user_id=command.user_id,
            api_key_id=command.api_key_id,
        )
        file_path = file_info.get("file_path")
        deleted_from_storage = False
        if file_path:
            try:
                deleted_from_storage = await delete_managed_file(storage_root, file_path)
            except FileDeletionSecurityError as exception:
                log_exception(
                    logger,
                    exception,
                    message="Security violation while deleting file",
                    operation=OPERATION,
                    details={"file_path": file_path, "file_id": command.file_id},
                )
                raise
        await database_files.delete_file(
            command.file_id,
            enforce_owner=True,
            user_id=command.user_id,
            api_key_id=command.api_key_id,
        )
        response_payload: JSONDict = {
            "id": command.file_id,
            "object": "file.deleted",
            "deleted": deleted_from_storage,
        }
        deliver_reply_event_or_raise(
            command.reply_channel,
            InferenceResultEvent(payload=response_payload),
            logger,
            operation=f"file delete response for '{command.file_id}'",
            overwrite_attempts=2,
        )

    await execute_or_error(
        command.reply_channel,
        f"File deletion for '{command.file_id}' failed",
        _action,
        task_registry=task_registry,
    )
