"""SoAI - Bounded video frame extraction [backend/core/media/frame_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ProcessError
from core.media.ffmpeg_arguments import build_ffmpeg_extraction_prefix
from core.media.frame_geometry import FrameTarget, map_jpeg_quality_to_ffmpeg_qscale
from core.media.process_runtime import run_media_process

__all__ = ("extract_video_frame",)


async def extract_video_frame(
    *,
    source_path: str,
    timestamp_seconds: float,
    target: FrameTarget,
    jpeg_quality: int,
    output_path: str,
    timeout_seconds: float,
) -> None:
    await run_media_process(
        (
            *build_ffmpeg_extraction_prefix(source_path, timestamp_seconds),
            "-frames:v",
            "1",
            "-vf",
            f"scale={target.width}:{target.height}:flags=bilinear",
            "-q:v",
            str(map_jpeg_quality_to_ffmpeg_qscale(jpeg_quality)),
            output_path,
        ),
        timeout_seconds=timeout_seconds,
        dependency_name="ffmpeg",
        operation_name="Video frame extraction",
        capture_stdout=False,
    )
    try:
        output_size = os.path.getsize(output_path)
    except OSError as exception:
        raise ProcessError(
            "Video frame extraction produced no output.", cause=exception
        ) from exception
    if output_size <= 0:
        raise ProcessError("Video frame extraction produced no output.")
