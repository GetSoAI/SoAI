"""SoAI - File retrieval query handler [backend/files/handlers/queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_files import FileRetrieveQuery
from core.events.types_models_streaming import InferenceResultEvent
from core.files.protocols import DatabaseFilesProtocol
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from files.command_execution import execute_or_error
from files.formatting import format_openai_file_object
from files.handlers.response import deliver_reply_event_or_raise
from files.lookup import get_file_info_or_fail

__all__ = ("handle_file_retrieve",)

LOGGER_NAME = "SoAI.files.handlers.queries"


async def handle_file_retrieve(
    command: FileRetrieveQuery,
    *,
    database_files: DatabaseFilesProtocol,
    task_registry: TaskRegistryProtocol,
) -> None:
    async def _action() -> None:
        logger = get_logger(LOGGER_NAME)
        file_info = await get_file_info_or_fail(
            database_files,
            command.file_id,
            enforce_owner=True,
            user_id=command.user_id,
            api_key_id=command.api_key_id,
        )
        response_payload = format_openai_file_object(file_info)
        deliver_reply_event_or_raise(
            command.reply_channel,
            InferenceResultEvent(payload=response_payload),
            logger,
            operation=f"file retrieve response for '{command.file_id}'",
            overwrite_attempts=2,
        )

    await execute_or_error(
        command.reply_channel,
        f"File retrieve query for '{command.file_id}' failed",
        _action,
        task_registry=task_registry,
    )
