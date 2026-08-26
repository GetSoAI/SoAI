"""SoAI - Browser download lifecycle support [backend/mcp/tools/browser/download_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_seconds_float
from core.validation.integers import is_strict_int
from mcp.tools.browser.download_records import (
    append_download_record,
    downloads_to_dicts,
    next_download_id,
    prune_download_records,
    sanitize_download_filename,
    update_download_record,
)
from mcp.tools.browser.download_tasks import spawn_download_saver_task
from mcp.tools.browser.types import PendingBrowserDownload

if TYPE_CHECKING:
    from playwright.async_api import Download

    from core.config.protocols import ConfigProtocol
    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "create_pending_download",
    "downloads_to_dicts",
    "drain_download_queue",
    "record_download_size_hint",
)


def record_download_size_hint(
    state: BrowserSessionState,
    *,
    url: str,
    content_length_header: str | None,
    max_entries: int,
) -> None:
    if not url:
        return
    if not isinstance(content_length_header, str) or not content_length_header.strip():
        return
    try:
        content_length = int(content_length_header.strip())
    except ValueError:
        return
    if content_length <= 0:
        return
    state.download_size_hints.append((url, content_length))
    if len(state.download_size_hints) > max_entries:
        overflow = len(state.download_size_hints) - max_entries
        state.download_size_hints = state.download_size_hints[overflow:]


def _lookup_download_size_hint(state: BrowserSessionState, *, url: str) -> int | None:
    if not url:
        return None
    for hinted_url, content_length in reversed(state.download_size_hints):
        if hinted_url == url:
            return content_length
    return None


def _queue_pending_download(
    pending: PendingBrowserDownload,
    *,
    downloads_dir: str | None,
    state: BrowserSessionState,
) -> None:
    download = pending.download
    download_id = next_download_id(state)
    download_url = str(download.url or "")
    suggested_filename = sanitize_download_filename(str(download.suggested_filename or "download"))
    append_download_record(
        state,
        download_id=download_id,
        url=download_url,
        suggested_filename=suggested_filename,
        status="pending",
        timestamp=pending.timestamp,
    )
    if downloads_dir is None:
        update_download_record(
            state,
            download_id=download_id,
            status="failed",
            file_path=None,
            error="Browser downloads directory is unavailable.",
        )
        return
    task = spawn_download_saver_task(
        state,
        pending,
        download_id=download_id,
        downloads_dir=downloads_dir,
        suggested_filename=suggested_filename,
        download_url=download_url,
    )
    state.download_tasks[download_id] = task


def _resolve_max_entries(config: ConfigProtocol) -> int:
    raw_limit = config.get_int("TOOLS.MCP.BROWSER.LOG_MAX_ENTRIES")
    if is_strict_int(raw_limit):
        return max(1, int(raw_limit))
    return 500


def _drain_queued_download_events(
    state: BrowserSessionState,
    *,
    downloads_dir: str | None,
) -> None:
    while True:
        try:
            pending = state.download_queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        _queue_pending_download(
            pending,
            downloads_dir=downloads_dir,
            state=state,
        )


def drain_download_queue(
    config: ConfigProtocol,
    state: BrowserSessionState,
    *,
    downloads_dir: str | None,
) -> None:
    effective_downloads_dir = downloads_dir or state.downloads_dir
    _drain_queued_download_events(
        state,
        downloads_dir=effective_downloads_dir,
    )
    prune_download_records(state, max_entries=_resolve_max_entries(config))


def create_pending_download(
    state: BrowserSessionState,
    download: Download,
) -> PendingBrowserDownload:
    download_url = str(download.url or "")
    return PendingBrowserDownload(
        download=download,
        timestamp=epoch_seconds_float(),
        expected_size_bytes=_lookup_download_size_hint(state, url=download_url),
    )
