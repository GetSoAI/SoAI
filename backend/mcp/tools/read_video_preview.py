"""SoAI - MCP read_video optional MP4 preview clip builder [backend/mcp/tools/read_video_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.media.frame_geometry import compute_frame_target
from core.media.job_storage import ensure_secure_directory, remove_media_file
from core.media.process_runtime import media_process_base_argv, run_media_process
from core.serialization.base64_values import encode_base64_ascii

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = ("ReadVideoPreviewJob", "ReadVideoPreviewResult", "build_preview_clip")

_PREVIEW_OPERATION = "mcp.tools.read_video.build_preview"
_PREVIEW_CONTENT_TYPE = "video/mp4"


@dataclass(frozen=True, slots=True)
class ReadVideoPreviewResult:
    video_base64: str
    content_type: str
    byte_size: int
    width: int
    height: int
    duration_seconds: float
    start_seconds: float
    includes_audio: bool


@dataclass(frozen=True, slots=True)
class ReadVideoPreviewJob:
    job_id: str
    source_path: str
    start_seconds: float
    range_end_seconds: float
    source_width: int
    source_height: int
    audio_present: bool
    include_audio: bool
    scratch_dir: str


def _audio_argv(job: ReadVideoPreviewJob) -> list[str]:
    if job.include_audio and job.audio_present:
        return ["-c:a", "aac", "-b:a", "96k"]
    return ["-an"]


def _build_preview_argv(
    job: ReadVideoPreviewJob,
    *,
    duration_seconds: float,
    target_width: int,
    target_height: int,
    crf: int,
    output_path: str,
) -> list[str]:
    return [
        *media_process_base_argv(),
        "-ss",
        f"{job.start_seconds:.6f}",
        "-i",
        job.source_path,
        "-t",
        f"{duration_seconds:.6f}",
        "-vf",
        f"scale={target_width}:{target_height}:flags=bilinear",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(crf),
        "-preset",
        "veryfast",
        *_audio_argv(job),
        "-movflags",
        "+faststart",
        output_path,
    ]


def _read_file_bytes(path: str) -> bytes:
    with open_binary(path, mode="rb") as handle:
        return handle.read()


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


async def build_preview_clip(
    job: ReadVideoPreviewJob,
    *,
    config: ReadVideoConfig,
    storage_manager: StorageManagerProtocol,
) -> ReadVideoPreviewResult | None:
    remaining = job.range_end_seconds - job.start_seconds
    duration = min(float(config.video_preview_seconds), remaining)
    if duration <= 0.0:
        return None
    target = compute_frame_target(
        job.source_width,
        job.source_height,
        config.video_preview_max_pixels,
    )
    ensure_secure_directory(job.scratch_dir)
    output_path = os.path.join(job.scratch_dir, "preview.mp4")
    reserve_estimate = max(1, config.video_preview_max_bytes) * max(
        1,
        config.temp_reservation_safety_multiplier,
    )
    try:
        with storage_manager.reserve_disk_space(
            path=output_path,
            required_bytes=reserve_estimate,
            operation=_PREVIEW_OPERATION,
            details={"job_id": job.job_id},
        ) as reservation:
            try:
                await run_media_process(
                    _build_preview_argv(
                        job,
                        duration_seconds=duration,
                        target_width=target.width,
                        target_height=target.height,
                        crf=config.video_preview_crf,
                        output_path=output_path,
                    ),
                    timeout_seconds=config.preview_extraction_timeout_sec,
                    dependency_name="ffmpeg",
                    operation_name="read_video preview extraction",
                    capture_stdout=False,
                )
            except SoAIError:
                return None
            actual = _file_size(output_path)
            if actual <= 0:
                return None
            if actual > config.video_preview_max_bytes:
                return None
            with claim_reserved_write(reservation, size_bytes=actual):
                data = _read_file_bytes(output_path)
    finally:
        remove_media_file(output_path)
    return ReadVideoPreviewResult(
        video_base64=encode_base64_ascii(data),
        content_type=_PREVIEW_CONTENT_TYPE,
        byte_size=actual,
        width=target.width,
        height=target.height,
        duration_seconds=duration,
        start_seconds=job.start_seconds,
        includes_audio=bool(job.include_audio and job.audio_present),
    )
