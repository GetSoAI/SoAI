"""SoAI - MCP read_video effective range and FPS resolution [backend/mcp/tools/read_video_range.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.media.types import VideoProbeResult
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = ("ReadVideoResolvedRange", "resolve_effective_range")

_MIN_RANGE_SPAN_SECONDS = 0.001


@dataclass(frozen=True, slots=True)
class ReadVideoResolvedRange:
    range_start_seconds: float
    range_end_seconds: float
    frames_per_second: float


def _resolve_end(probe: VideoProbeResult, end_seconds: float | None) -> float:
    if end_seconds is None:
        return probe.duration_seconds
    return min(float(end_seconds), probe.duration_seconds)


def _resolve_fps(requested_fps: float | None, config: ReadVideoConfig) -> float:
    raw = config.default_frames_per_second if requested_fps is None else float(requested_fps)
    if raw <= 0.0:
        raise MCPToolError(-32602, "read_video frames_per_second must be greater than 0.")
    return min(raw, config.max_frames_per_second)


def resolve_effective_range(
    probe: VideoProbeResult,
    *,
    start_seconds: float,
    end_seconds: float | None,
    requested_fps: float | None,
    config: ReadVideoConfig,
) -> ReadVideoResolvedRange:
    start = float(start_seconds)
    if start < 0.0:
        raise MCPToolError(-32602, "read_video start_seconds must be greater than or equal to 0.")
    end = _resolve_end(probe, end_seconds)
    if end <= start or (end - start) < _MIN_RANGE_SPAN_SECONDS:
        raise MCPToolError(
            -32602,
            "read_video selected range is empty after clamping to the source duration.",
        )
    fps = _resolve_fps(requested_fps, config)
    return ReadVideoResolvedRange(
        range_start_seconds=start,
        range_end_seconds=end,
        frames_per_second=fps,
    )
