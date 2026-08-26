"""SoAI - MCP read_video live progress tracking and lease renewal [backend/mcp/tools/read_video_progress_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.read_video.operations import ReadVideoProgressUpdate
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = ("LEASE_TTL_MS", "ReadVideoProgressTracker", "resolve_read_video_lease_ttl_ms")

LEASE_TTL_MS = 600_000
_LEASE_OPERATION_MARGIN_MS = 60_000
_HEARTBEAT_DIVISOR = 3.0
_MIN_HEARTBEAT_INTERVAL_SECONDS = 5.0


def resolve_read_video_lease_ttl_ms(config: ReadVideoConfig) -> int:
    max_operation_timeout_sec = max(
        config.frame_extraction_timeout_sec,
        config.audio_extraction_timeout_sec,
        config.preview_extraction_timeout_sec,
    )
    return max(LEASE_TTL_MS, max_operation_timeout_sec * 1000 + _LEASE_OPERATION_MARGIN_MS)


def _heartbeat_interval_seconds(config: ReadVideoConfig) -> float:
    return max(
        _MIN_HEARTBEAT_INTERVAL_SECONDS,
        resolve_read_video_lease_ttl_ms(config) / 1000.0 / _HEARTBEAT_DIVISOR,
    )


class ReadVideoProgressTracker:
    def __init__(
        self,
        *,
        repository: DatabaseReadVideoJobsProtocol,
        job_id: str,
        lease_token: str,
        config: ReadVideoConfig,
        on_progress: Callable[[ReadVideoProgressUpdate], Awaitable[None]],
        clock: Callable[[], int],
        range_start_seconds: float,
        frames_per_second: float,
    ) -> None:
        self._repository = repository
        self._job_id = job_id
        self._lease_token = lease_token
        self._config = config
        self._on_progress = on_progress
        self._clock = clock
        self._range_start_seconds = range_start_seconds
        self._frames_per_second = frames_per_second
        self._stage: str | None = None
        self._frames_done = 0
        self._frames_total = 0
        self._audio_done = 0
        self._audio_total = 0
        self._current_timestamp_seconds: float | None = None
        self._last_publish_monotonic: float | None = None

    def set_stage(self, stage: str) -> None:
        self._stage = stage

    async def on_frames(self, done: int, total: int) -> None:
        self._frames_done = done
        self._frames_total = total
        if done > 0 and self._frames_per_second > 0:
            self._current_timestamp_seconds = (
                self._range_start_seconds + (done - 1) / self._frames_per_second
            )
        await self._flush(force=False)

    async def on_audio(self, done: int, total: int) -> None:
        self._audio_done = done
        self._audio_total = total
        await self._flush(force=False)

    async def flush_now(self) -> None:
        await self._flush(force=True)

    async def run_lease_heartbeat(self) -> None:
        interval_seconds = _heartbeat_interval_seconds(self._config)
        while True:
            await asyncio.sleep(interval_seconds)
            await self._renew_lease(self._clock())

    def _compute_percent(self) -> float:
        total_units = self._frames_total + self._audio_total
        if total_units <= 0:
            return 0.0
        done_units = self._frames_done + self._audio_done
        percent = (done_units / total_units) * 100.0
        return max(0.0, min(100.0, percent))

    def _build_update(self, now_ms: int) -> ReadVideoProgressUpdate:
        return ReadVideoProgressUpdate(
            job_id=self._job_id,
            lease_token=self._lease_token,
            now_ms=now_ms,
            stage=self._stage,
            percent_complete=self._compute_percent(),
            frames_done=self._frames_done,
            frames_total_estimate=self._frames_total or None,
            audio_chunks_done=self._audio_done,
            audio_chunks_total_estimate=self._audio_total or None,
            current_timestamp_seconds=self._current_timestamp_seconds,
        )

    def _should_publish(self, force: bool) -> bool:
        if force:
            return True
        now = time.monotonic()
        if self._last_publish_monotonic is None:
            return True
        interval = self._config.live_progress_min_interval_ms / 1000.0
        return (now - self._last_publish_monotonic) >= interval

    async def _flush(self, force: bool) -> None:
        now_ms = self._clock()
        update = self._build_update(now_ms)
        await self._repository.update_progress(update)
        await self._renew_lease(now_ms)
        if not self._should_publish(force):
            return
        await self._on_progress(update)
        self._last_publish_monotonic = time.monotonic()

    async def _renew_lease(self, now_ms: int) -> None:
        renewed = await self._repository.renew_lease(
            self._job_id,
            self._lease_token,
            now_ms + resolve_read_video_lease_ttl_ms(self._config),
            now_ms,
        )
        if not renewed:
            raise MCPToolError(-32603, "read_video lost its durable processing lease.")
