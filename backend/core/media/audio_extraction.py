"""SoAI - Bounded FFmpeg audio chunk extraction [backend/core/media/audio_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ProcessError
from core.media.ffmpeg_arguments import build_ffmpeg_extraction_prefix
from core.media.process_runtime import run_media_process
from core.media.types import AudioChunk

__all__ = ("estimate_wav_bytes", "extract_audio_chunk")

_WAV_BYTES_PER_SECOND = 32_000.0
_WAV_HEADER_BYTES = 1_024


def estimate_wav_bytes(duration_seconds: float, safety_multiplier: int) -> int:
    payload_bytes = int(_WAV_BYTES_PER_SECOND * max(0.0, duration_seconds))
    return (payload_bytes + _WAV_HEADER_BYTES) * max(1, safety_multiplier)


async def extract_audio_chunk(
    *,
    source_path: str,
    chunk: AudioChunk,
    output_path: str,
    timeout_seconds: float,
) -> None:
    await run_media_process(
        (
            *build_ffmpeg_extraction_prefix(source_path, chunk.start_seconds),
            "-t",
            f"{chunk.end_seconds - chunk.start_seconds:.6f}",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_path,
        ),
        timeout_seconds=timeout_seconds,
        dependency_name="ffmpeg",
        operation_name="Audio extraction",
        capture_stdout=False,
    )
    try:
        output_size = os.path.getsize(output_path)
    except OSError as exception:
        raise ProcessError("Audio extraction produced no output.", cause=exception) from exception
    if output_size <= 0:
        raise ProcessError("Audio extraction produced no output.")
