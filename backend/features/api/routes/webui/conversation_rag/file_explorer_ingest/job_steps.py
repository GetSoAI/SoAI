"""SoAI - WebUI File Explorer to RAG ingest job steps [backend/features/api/routes/webui/conversation_rag/file_explorer_ingest/job_steps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.status_transitions import update_progress
from features.api.routes.webui.conversation_rag.file_explorer_ingest.path_formatting import (
    join_virtual_path,
)

if TYPE_CHECKING:
    from core.files.explorer_models import FileEntryInfo
    from core.files.protocols_explorer import (
        FileExplorerCoreProtocol,
        FileSystemRootScopeProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = (
    "count_files_under_path",
    "iter_directory_entries",
    "iter_file_entries_under_path",
)

OPERATION_LIST_DIRECTORY = "webui.conversation_rag.file_explorer_ingest.list_directory"


async def iter_directory_entries(
    *,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    virtual_path: str,
    limit: int = 1000,
) -> AsyncIterator[FileEntryInfo]:
    offset = 0
    while True:
        page = await file_explorer_core.list_directory(
            root_scope,
            virtual_path,
            offset=offset,
            limit=limit,
        )
        for entry in page.entries:
            yield entry
        offset = int(page.offset) + int(page.limit)
        if offset >= int(page.total):
            return


async def iter_file_entries_under_path(
    *,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    root_virtual_path: str,
    recursive: bool,
    logger: TraceLogger,
    task_id: str,
    operation: str,
) -> AsyncIterator[tuple[str, FileEntryInfo]]:
    dirs: list[str] = [root_virtual_path]
    while dirs:
        current = dirs.pop()
        entries = iter_directory_entries(
            file_explorer_core=file_explorer_core,
            root_scope=root_scope,
            virtual_path=current,
        )
        try:
            async for entry in entries:
                if entry.is_directory:
                    if recursive:
                        dirs.append(join_virtual_path(current, entry.name))
                    continue
                yield join_virtual_path(current, entry.name), entry
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to list directory during RAG File Explorer ingestion.",
                operation=operation,
                details={"path": current, "task_id": task_id},
            )
            continue


async def count_files_under_path(
    *,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    root_virtual_path: str,
    recursive: bool,
    max_file_bytes: int,
    logger: TraceLogger,
    task_registry: TaskRegistryProtocol,
    task_id: str,
) -> tuple[int, int, int]:
    total_files = 0
    skipped_oversize = 0
    total_bytes = 0
    async for _virtual_file_path, entry in iter_file_entries_under_path(
        file_explorer_core=file_explorer_core,
        root_scope=root_scope,
        root_virtual_path=root_virtual_path,
        recursive=recursive,
        logger=logger,
        task_id=task_id,
        operation=OPERATION_LIST_DIRECTORY,
    ):
        total_files += 1
        if int(entry.size) > max_file_bytes:
            skipped_oversize += 1
            continue
        total_bytes += max(0, int(entry.size))
    await update_progress(
        task_registry,
        task_id,
        progress_current=5,
        percent_override=5,
        status_message="Scanning",
        details=f"Files: {total_files} • Skipped: {skipped_oversize}",
    )
    return total_files, skipped_oversize, total_bytes
