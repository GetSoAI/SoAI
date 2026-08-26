"""SoAI - MCP read_video audio extraction and transcription processor [backend/mcp/tools/read_video_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError, StateError
from core.mcp.protocols_main import ReadAudioGatewayProtocol
from core.media.audio_extraction import estimate_wav_bytes
from core.media.job_storage import ensure_secure_directory, remove_media_file
from core.media.process_runtime import media_process_base_argv, run_media_process
from mcp.tools.read_video_audio_mapping import compute_audio_chunks, map_chunk_segments

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.read_video.operations import ReadVideoAudioChunkReservation
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = ("ReadVideoAudioJob", "extract_audio")

_SEGMENT_INDEX_STRIDE = 1_000_000


@dataclass(frozen=True, slots=True)
class ReadVideoAudioJob:
    job_id: str
    source_path: str
    range_start_seconds: float
    range_end_seconds: float
    audio_dir: str
    scratch_dir: str


def _build_wav_argv(
    source_path: str,
    start_seconds: float,
    duration_seconds: float,
    wav_path: str,
) -> list[str]:
    return [
        *media_process_base_argv(),
        "-ss",
        f"{start_seconds:.6f}",
        "-i",
        source_path,
        "-t",
        f"{duration_seconds:.6f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        wav_path,
    ]


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


async def _process_one_chunk(
    job: ReadVideoAudioJob,
    *,
    chunk: ReadVideoAudioChunkReservation,
    config: ReadVideoConfig,
    repository: DatabaseReadVideoJobsProtocol,
    storage_manager: StorageManagerProtocol,
    transcriber: ReadAudioGatewayProtocol,
) -> None:
    duration = chunk.end_seconds - chunk.start_seconds
    if duration <= 0:
        await repository.complete_audio_chunk(job.job_id, chunk.chunk_index, "", ())
        return
    wav_path = os.path.join(job.scratch_dir, f"audio_{chunk.chunk_index:06d}.wav")
    estimate = estimate_wav_bytes(duration, config.temp_reservation_safety_multiplier)
    try:
        with storage_manager.reserve_disk_space(
            path=wav_path,
            required_bytes=estimate,
            operation="mcp.tools.read_video.audio_chunk",
            details={"job_id": job.job_id, "chunk_index": chunk.chunk_index},
        ) as reservation:
            try:
                await run_media_process(
                    _build_wav_argv(job.source_path, chunk.start_seconds, duration, wav_path),
                    timeout_seconds=config.audio_extraction_timeout_sec,
                    dependency_name="ffmpeg",
                    operation_name="read_video audio extraction",
                    capture_stdout=False,
                )
            except SoAIError as exception:
                await repository.fail_audio_chunk(job.job_id, chunk.chunk_index, exception.message)
                return
            actual = _file_size(wav_path)
            if actual <= 0:
                await repository.fail_audio_chunk(
                    job.job_id,
                    chunk.chunk_index,
                    "audio extraction produced no output",
                )
                return
            with reservation.claim_write_bytes(actual) as claim:
                claim.commit()
            payload = await transcriber.read_audio(
                file_path=wav_path,
                model_name=config.whisper_model,
                language=None,
                task="transcribe",
                include_word_timestamps=False,
            )
        text, segments = map_chunk_segments(
            payload,
            chunk=chunk,
            range_start_seconds=job.range_start_seconds,
            range_end_seconds=job.range_end_seconds,
            segment_stride=_SEGMENT_INDEX_STRIDE,
        )
        if len(segments) >= _SEGMENT_INDEX_STRIDE:
            raise StateError("read_video audio chunk produced too many segments.")
        await repository.complete_audio_chunk(job.job_id, chunk.chunk_index, text, segments)
    finally:
        remove_media_file(wav_path)


async def extract_audio(
    job: ReadVideoAudioJob,
    *,
    config: ReadVideoConfig,
    repository: DatabaseReadVideoJobsProtocol,
    storage_manager: StorageManagerProtocol,
    transcriber: ReadAudioGatewayProtocol,
    on_progress: Callable[[int, int], Awaitable[None]],
) -> None:
    chunks = compute_audio_chunks(
        job.range_start_seconds,
        job.range_end_seconds,
        config.audio_chunk_seconds,
    )
    total = len(chunks)
    await repository.reserve_audio_chunks(job.job_id, chunks)
    completed = await repository.get_completed_chunk_indices(job.job_id)
    await on_progress(len(completed), total)
    ensure_secure_directory(job.audio_dir)
    ensure_secure_directory(job.scratch_dir)
    for chunk in chunks:
        if chunk.chunk_index in completed:
            continue
        await _process_one_chunk(
            job,
            chunk=chunk,
            config=config,
            repository=repository,
            storage_manager=storage_manager,
            transcriber=transcriber,
        )
        done = len(await repository.get_completed_chunk_indices(job.job_id))
        await on_progress(done, total)
