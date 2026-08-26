"""SoAI - Browser download task state mutations [backend/mcp/tools/browser/download_task_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.browser.download_records import update_download_record
from mcp.tools.browser.download_target_paths import allocate_download_target_path

if TYPE_CHECKING:
    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "allocate_download_task_target_path",
    "record_download_task_status",
)


async def record_download_task_status(
    state: BrowserSessionState,
    *,
    download_id: str,
    status: str,
    file_path: str | None,
    error: str | None,
    target_path: str | None,
    remove_task: bool,
) -> None:
    async with state.lock:
        update_download_record(
            state,
            download_id=download_id,
            status=status,
            file_path=file_path,
            error=error,
        )
        if target_path is not None:
            state.download_target_paths.discard(target_path)
        if remove_task:
            state.download_tasks.pop(download_id, None)


async def allocate_download_task_target_path(
    state: BrowserSessionState,
    *,
    downloads_dir: str,
    suggested_filename: str,
) -> str:
    async with state.lock:
        return allocate_download_target_path(
            downloads_dir=downloads_dir,
            filename=suggested_filename,
            reserved_paths=state.download_target_paths,
        )
