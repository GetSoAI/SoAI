"""SoAI - Browser download record state helpers [backend/mcp/tools/browser/download_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONDict
from mcp.tools.browser.types import BrowserDownload

if TYPE_CHECKING:
    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "append_download_record",
    "downloads_to_dicts",
    "next_download_id",
    "prune_download_records",
    "sanitize_download_filename",
    "update_download_record",
)


def downloads_to_dicts(downloads: list[BrowserDownload]) -> list[JSONDict]:
    output: list[JSONDict] = []
    for item in downloads:
        payload: JSONDict = {
            "download_id": item.download_id,
            "url": item.url,
            "suggested_filename": item.suggested_filename,
            "status": item.status,
            "timestamp": item.timestamp,
        }
        if item.file_path is not None:
            payload["file_path"] = item.file_path
        if item.error is not None:
            payload["error"] = item.error
        output.append(payload)
    return output


def sanitize_download_filename(filename: str) -> str:
    stripped = filename.strip().replace("\\", "/")
    parts = [segment for segment in stripped.split("/") if segment]
    if not parts:
        return "download"
    sanitized = parts[-1].strip()
    if not sanitized or sanitized in {".", ".."}:
        return "download"
    return sanitized


def next_download_id(state: BrowserSessionState) -> str:
    download_id = f"dl{state.next_download_id}"
    state.next_download_id += 1
    return download_id


def append_download_record(
    state: BrowserSessionState,
    *,
    download_id: str,
    url: str,
    suggested_filename: str,
    status: str,
    timestamp: float,
) -> None:
    state.downloads.append(
        BrowserDownload(
            download_id=download_id,
            url=url,
            suggested_filename=suggested_filename,
            file_path=None,
            status=status,
            error=None,
            timestamp=timestamp,
        ),
    )


def update_download_record(
    state: BrowserSessionState,
    *,
    download_id: str,
    status: str,
    file_path: str | None,
    error: str | None,
) -> None:
    updated: list[BrowserDownload] = []
    for item in state.downloads:
        if item.download_id == download_id:
            updated.append(
                BrowserDownload(
                    download_id=item.download_id,
                    url=item.url,
                    suggested_filename=item.suggested_filename,
                    file_path=file_path,
                    status=status,
                    error=error,
                    timestamp=item.timestamp,
                ),
            )
        else:
            updated.append(item)
    state.downloads = updated


def prune_download_records(state: BrowserSessionState, *, max_entries: int) -> None:
    if len(state.downloads) <= max_entries:
        return
    protected_ids = set(state.download_tasks)
    terminal_records = [item for item in state.downloads if item.download_id not in protected_ids]
    if not terminal_records:
        return
    removable_count = min(len(state.downloads) - max_entries, len(terminal_records))
    removable_ids = {item.download_id for item in terminal_records[:removable_count]}
    state.downloads = [item for item in state.downloads if item.download_id not in removable_ids]
