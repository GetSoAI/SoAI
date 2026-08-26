"""SoAI - Post-task temporary file cleanup [backend/orchestrator/execution/temp_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.files.path_policy import ensure_path_within_base, is_same_path
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = (
    "cleanup_task_temp_files",
    "extract_temp_paths_from_metadata",
    "is_safe_temp_path",
)

LOGGER_NAME = "SoAI.orchestrator.execution.temp_cleanup"
OPERATION = "orchestrator.temp_cleanup.cleanup_task_temp_files"


TEMP_PATH_METADATA_KEYS: tuple[str, ...] = (
    "temp_file_path",
    "image_temp_paths",
    "mask_temp_path",
)


def extract_temp_paths_from_metadata(task: Task) -> Sequence[str]:
    paths: list[str] = []
    metadata = task.metadata
    if not metadata:
        return paths
    for key in TEMP_PATH_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
            continue
        if isinstance(value, list | tuple):
            for entry in value:
                if isinstance(entry, str) and entry.strip():
                    paths.append(entry.strip())
    return paths


def is_safe_temp_path(path: str, temp_directory: str | None) -> bool:
    if not isinstance(path, str) or not path:
        return False
    if not os.path.isabs(path):
        return False
    if not isinstance(temp_directory, str):
        return False
    try:
        resolved_path = ensure_path_within_base(
            temp_directory,
            path,
            description="Temporary cleanup path",
        )
        resolved_temp_directory = os.path.realpath(os.path.abspath(temp_directory))
        return not is_same_path(resolved_path, resolved_temp_directory)
    except (OSError, ValueError, TypeError):
        return False


async def cleanup_task_temp_files(task: Task, temp_directory: str | None) -> None:
    logger = get_logger(LOGGER_NAME)
    paths = extract_temp_paths_from_metadata(task)
    if not paths:
        return
    for path in paths:
        if not is_safe_temp_path(path, temp_directory):
            logger.debug(
                "Skipping temp file cleanup for task [%s]: path '%s' is outside temp directory.",
                task.task_id,
                path,
            )
            continue
        try:
            await async_remove_if_exists(path)
            logger.debug(
                "Cleaned up temp file for task [%s]: %s",
                task.task_id,
                path,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to clean up temp file (non-critical).",
                operation=OPERATION,
                details={"task_id": task.task_id, "path": path},
                level="debug",
            )
