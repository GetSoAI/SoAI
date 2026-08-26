"""SoAI - File explorer download archive cancellation [backend/features/file_explorer/download_archive_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from threading import Event

from core.concurrency.cancellation import TaskCancelledError

__all__ = ("raise_if_download_archive_cancelled",)


def raise_if_download_archive_cancelled(cancellation_event: Event) -> None:
    if cancellation_event.is_set():
        raise TaskCancelledError(
            "file_explorer_download_archive",
            "File explorer download was cancelled.",
        )
