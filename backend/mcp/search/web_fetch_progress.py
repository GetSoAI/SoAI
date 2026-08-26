"""SoAI - MCP web fetch task progress reporting [backend/mcp/search/web_fetch_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.progress.formatting import (
    calculate_eta,
    format_transfer_details,
    format_transfer_status_message,
)
from core.progress.speed import SpeedCalculator
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.status_transitions import update_progress
from mcp.progress_reporting import compute_progress_update

__all__ = ("WebFetchTaskProgressReporter",)


class WebFetchTaskProgressReporter:
    def __init__(
        self,
        *,
        task_registry: TaskRegistryProtocol,
        task_id: str,
        progress_start: int,
        progress_end: int,
        fetch_label: str,
        max_size_bytes: int,
    ) -> None:
        self._task_registry = task_registry
        self._task_id = task_id
        self._progress_start = int(progress_start)
        self._progress_end = int(progress_end)
        self._fetch_label = fetch_label
        self._max_size_bytes = int(max_size_bytes)
        self._speed_calc = SpeedCalculator()
        self._last_reported_percent = -1
        self._last_reported_at = 0.0
        self._last_reported_bytes = 0

    @property
    def last_reported_bytes(self) -> int:
        return self._last_reported_bytes

    @property
    def speed(self) -> float:
        return self._speed_calc.speed

    async def __call__(self, downloaded_bytes: int, total_bytes: int | None, _: str) -> None:
        effective_total = (
            total_bytes if total_bytes and total_bytes > 0 else int(self._max_size_bytes)
        )
        downloaded = max(0, int(downloaded_bytes))
        scaled_percent, should_report, timestamp = compute_progress_update(
            current=downloaded,
            total=effective_total,
            progress_start=self._progress_start,
            progress_end=self._progress_end,
            last_reported_percent=self._last_reported_percent,
            last_reported_at=self._last_reported_at,
            last_reported_bytes=self._last_reported_bytes,
        )
        if not should_report:
            return
        speed = self._speed_calc.update(downloaded)
        eta_seconds = (
            calculate_eta(speed, downloaded, total_bytes)
            if total_bytes and total_bytes > 0
            else 0.0
        )
        message = format_transfer_status_message(
            "Downloading",
            self._fetch_label,
            downloaded_size=downloaded,
            total_size=total_bytes if total_bytes and total_bytes > 0 else None,
            speed=speed,
            eta_seconds=eta_seconds,
        )
        details = format_transfer_details(
            downloaded,
            total_bytes if total_bytes and total_bytes > 0 else None,
            speed=speed,
            eta_seconds=eta_seconds,
        )
        self._last_reported_percent = scaled_percent
        self._last_reported_at = timestamp
        self._last_reported_bytes = downloaded
        await update_progress(
            self._task_registry,
            self._task_id,
            progress_current=scaled_percent,
            status_message=message,
            details=details,
        )
