"""SoAI - MCP read_video frame extraction processor [backend/mcp/tools/read_video_frames.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.media.frame_geometry import (
    FrameTarget,
    compute_frame_target,
    compute_frame_timestamps,
    map_jpeg_quality_to_ffmpeg_qscale,
)
from core.media.job_storage import ensure_secure_directory, remove_media_file
from core.media.process_runtime import media_process_base_argv, run_media_process
from core.read_video.operations import (
    ReadVideoFrameCompletion,
    ReadVideoFrameReservation,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = ("ReadVideoFrameJob", "extract_frames")

_FRAME_OPERATION = "mcp.tools.read_video.extract_frame"


@dataclass(frozen=True, slots=True)
class ReadVideoFrameJob:
    job_id: str
    source_path: str
    range_start_seconds: float
    range_end_seconds: float
    frames_per_second: float
    source_width: int
    source_height: int
    frames_dir: str
    scratch_dir: str


def _build_frame_argv(
    job: ReadVideoFrameJob,
    timestamp_seconds: float,
    target: FrameTarget,
    qscale: int,
    scratch_path: str,
) -> list[str]:
    return [
        *media_process_base_argv(),
        "-ss",
        f"{timestamp_seconds:.6f}",
        "-i",
        job.source_path,
        "-frames:v",
        "1",
        "-vf",
        f"scale={target.width}:{target.height}:flags=bilinear",
        "-q:v",
        str(qscale),
        scratch_path,
    ]


def _scratch_has_output(scratch_path: str) -> bool:
    try:
        return os.path.getsize(scratch_path) > 0
    except OSError:
        return False


async def _extract_one_frame(
    job: ReadVideoFrameJob,
    *,
    frame_index: int,
    timestamp_seconds: float,
    target: FrameTarget,
    qscale: int,
    timeout_sec: int,
    storage_manager: StorageManagerProtocol,
    repository: DatabaseReadVideoJobsProtocol,
) -> None:
    scratch_path = os.path.join(job.scratch_dir, f"frame_{frame_index:06d}.jpg")
    artifact_path = os.path.join(job.frames_dir, f"frame_{frame_index:06d}.jpg")
    await run_media_process(
        _build_frame_argv(job, timestamp_seconds, target, qscale, scratch_path),
        timeout_seconds=timeout_sec,
        dependency_name="ffmpeg",
        operation_name="read_video frame extraction",
        capture_stdout=False,
    )
    if not _scratch_has_output(scratch_path):
        await run_media_process(
            _build_frame_argv(job, job.range_start_seconds, target, qscale, scratch_path),
            timeout_seconds=timeout_sec,
            dependency_name="ffmpeg",
            operation_name="read_video frame extraction",
            capture_stdout=False,
        )
    if not _scratch_has_output(scratch_path):
        remove_media_file(scratch_path)
        await repository.fail_frame(job.job_id, frame_index, "frame extraction produced no output")
        return
    with open_binary(scratch_path, mode="rb") as scratch_handle:
        data = scratch_handle.read()
    size = len(data)
    encoded_chars = ((size + 2) // 3) * 4
    with (
        storage_manager.reserve_disk_space(
            path=artifact_path,
            required_bytes=size,
            operation="mcp.tools.read_video.frame_artifact",
            details={"job_id": job.job_id, "frame_index": frame_index},
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=size),
    ):
        with open_binary(artifact_path, mode="wb") as artifact_handle:
            artifact_handle.write(data)
    await repository.complete_frame(
        ReadVideoFrameCompletion(
            job_id=job.job_id,
            frame_index=frame_index,
            artifact_path=artifact_path,
            content_type="image/jpeg",
            byte_size=size,
            encoded_chars=encoded_chars,
            width=target.width,
            height=target.height,
            source_width=job.source_width,
            source_height=job.source_height,
        ),
    )
    remove_media_file(scratch_path)


async def extract_frames(
    job: ReadVideoFrameJob,
    *,
    config: ReadVideoConfig,
    repository: DatabaseReadVideoJobsProtocol,
    storage_manager: StorageManagerProtocol,
    on_progress: Callable[[int, int], Awaitable[None]],
) -> None:
    timestamps = compute_frame_timestamps(
        job.range_start_seconds,
        job.range_end_seconds,
        job.frames_per_second,
    )
    total = len(timestamps)
    await repository.reserve_frames(
        job.job_id,
        tuple(
            ReadVideoFrameReservation(frame_index=index, timestamp_seconds=timestamp)
            for index, timestamp in enumerate(timestamps)
        ),
    )
    completed = await repository.get_completed_frame_indices(job.job_id)
    await on_progress(len(completed), total)
    target = compute_frame_target(job.source_width, job.source_height, config.max_frame_pixels)
    qscale = map_jpeg_quality_to_ffmpeg_qscale(config.jpeg_quality)
    ensure_secure_directory(job.frames_dir)
    ensure_secure_directory(job.scratch_dir)
    pending = [
        (index, timestamp) for index, timestamp in enumerate(timestamps) if index not in completed
    ]
    page_size = config.frame_page_size
    for batch_start in range(0, len(pending), page_size):
        batch = pending[batch_start : batch_start + page_size]
        for frame_index, timestamp in batch:
            await _extract_one_frame(
                job,
                frame_index=frame_index,
                timestamp_seconds=timestamp,
                target=target,
                qscale=qscale,
                timeout_sec=config.frame_extraction_timeout_sec,
                storage_manager=storage_manager,
                repository=repository,
            )
        done = await repository.count_completed_frames(job.job_id)
        await on_progress(done, total)
