"""SoAI - Download and task progress tracking for plugins [backend/plugin_sdk/contracts/progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from core.config.byte_sizes import MIB_BYTES
from core.logging.trace import get_logger
from core.progress.formatting import (
    calculate_eta,
    format_transfer_details,
    format_transfer_log_suffix,
)
from core.progress.progress_bar import format_progress_bar
from core.progress.speed import SpeedCalculator

if TYPE_CHECKING:
    type ProgressCallback = Callable[[ProgressPayload], None]
    type AsyncProgressCallback = Callable[[ProgressPayload], Awaitable[None]]

__all__ = (
    "DownloadProgressReporter",
    "DownloadStatsPayload",
    "ProgressPayload",
    "SpeedCalculator",
    "format_progress_bar",
    "get_progress_payload",
)

LOGGER_NAME = "SoAI.plugin_sdk.contracts.progress"


class ProgressPayload(TypedDict):
    type: str
    component: str
    percent: int
    message: str
    details: str


class DownloadStatsPayload(TypedDict):
    bytes_downloaded: int
    duration_ms: int
    bytes_per_second: float


@dataclass(slots=True)
class DownloadProgressReporter:
    component: str
    filename: str
    total_size: int
    output_callback: ProgressCallback | AsyncProgressCallback | None = None
    progress_start: int = field(default=0)
    progress_end: int = field(default=100)
    downloaded_bytes: int = field(default=0, repr=False, init=False)
    _last_percent: int = field(default=-1, repr=False, init=False)
    _last_reported_at: float = field(default=0.0, repr=False, init=False)
    _speed_calc: SpeedCalculator = field(default_factory=SpeedCalculator, repr=False, init=False)
    _start_time: float = field(default=0.0, repr=False, init=False)

    def __post_init__(self) -> None:
        self._start_time = time.monotonic()

    def _calculate_percent(self) -> int:
        if self.total_size <= 0:
            return self.progress_start
        file_percent = int(self.downloaded_bytes / self.total_size * 100)
        return int(
            self.progress_start + file_percent / 100 * (self.progress_end - self.progress_start),
        )

    def _calculate_eta(self, speed: float) -> float:
        return calculate_eta(speed, self.downloaded_bytes, self.total_size)

    def _build_payload(self) -> ProgressPayload | None:
        percent = self._calculate_percent()
        speed = self._speed_calc.update(self.downloaded_bytes)
        eta_seconds = self._calculate_eta(speed)
        elapsed_seconds = time.monotonic() - self._start_time
        payload = get_progress_payload(
            self.component,
            self.filename,
            percent,
            self._last_percent,
            self.downloaded_bytes,
            self.total_size,
            speed=speed,
            eta_seconds=eta_seconds,
            last_reported_at=self._last_reported_at,
            elapsed_seconds=elapsed_seconds,
        )
        if payload:
            self._last_percent = payload["percent"]
            self._last_reported_at = time.monotonic()
        return payload

    def report_sync(self, chunk_size: int) -> ProgressPayload | None:
        self.downloaded_bytes += chunk_size
        return self._build_payload()

    async def report_async(self, chunk_size: int) -> None:
        payload = self.report_sync(chunk_size)
        if payload and self.output_callback:
            result = self.output_callback(payload)
            if inspect.isawaitable(result):
                await result

    def finalize_sync(self) -> ProgressPayload | None:
        if self._last_percent < self.progress_end:
            reported_total = self.total_size if self.total_size > 0 else self.downloaded_bytes
            elapsed_seconds = time.monotonic() - self._start_time
            self._speed_calc.update(self.downloaded_bytes, force_sample=True)
            return get_progress_payload(
                self.component,
                self.filename,
                self.progress_end,
                self._last_percent,
                self.downloaded_bytes,
                reported_total,
                speed=self._speed_calc.speed,
                eta_seconds=0.0,
                last_reported_at=self._last_reported_at,
                elapsed_seconds=elapsed_seconds,
            )
        return None

    async def finalize_async(self) -> None:
        payload = self.finalize_sync()
        if payload and self.output_callback:
            result = self.output_callback(payload)
            if inspect.isawaitable(result):
                await result

    def reset(self) -> None:
        self.downloaded_bytes = 0
        self._last_percent = -1
        self._last_reported_at = 0.0
        self._speed_calc.reset()
        self._start_time = time.monotonic()

    @property
    def download_stats(self) -> DownloadStatsPayload:
        elapsed = time.monotonic() - self._start_time
        bytes_per_second = self.downloaded_bytes / elapsed if elapsed > 0 else 0.0
        return {
            "bytes_downloaded": self.downloaded_bytes,
            "duration_ms": max(0, int(elapsed * 1000)),
            "bytes_per_second": bytes_per_second,
        }


def get_progress_payload(
    component: str,
    filename: str,
    percent: int,
    last_reported_percent: int,
    downloaded_size: int = 0,
    total_size: int = 0,
    speed: float = 0.0,
    eta_seconds: float = 0.0,
    *,
    last_reported_at: float = 0.0,
    min_interval_seconds: float = 60.0,
    elapsed_seconds: float = 0.0,
) -> ProgressPayload | None:
    logger_progress = get_logger(LOGGER_NAME)
    now = time.monotonic()
    if percent < last_reported_percent:
        return None
    downloaded_mb = downloaded_size / MIB_BYTES if downloaded_size > 0 else None
    total_mb = total_size / MIB_BYTES if total_size > 0 else None
    message = f"Downloading {filename}"
    details = format_transfer_details(
        downloaded_size,
        total_size if total_size > 0 else None,
        speed=speed,
        eta_seconds=eta_seconds,
    )
    time_since_last_report = now - last_reported_at
    should_show = False
    if (
        percent == 100
        or 0 < min_interval_seconds <= time_since_last_report
        or (percent != last_reported_percent and time_since_last_report >= 1.0)
    ):
        should_show = True
    if not should_show:
        return None
    log_suffix = format_transfer_log_suffix(speed, eta_seconds, elapsed_seconds)
    logger_progress.info(
        "[%s] %s %s%s",
        component.capitalize(),
        message,
        format_progress_bar(percent, downloaded_mb, total_mb),
        log_suffix,
    )
    return {
        "type": "progress",
        "component": component,
        "percent": percent,
        "message": message,
        "details": details,
    }
