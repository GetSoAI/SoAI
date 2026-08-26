"""SoAI - MCP read_video audio chunk planning and segment mapping [backend/mcp/tools/read_video_audio_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.read_video.operations import (
    ReadVideoAudioChunkReservation,
    ReadVideoAudioSegmentValue,
)
from mcp.tools.read_audio_transcript import json_float

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "compute_audio_chunks",
    "map_chunk_segments",
)

_MIN_CHUNK_SECONDS = 1e-3


def compute_audio_chunks(
    range_start_seconds: float,
    range_end_seconds: float,
    chunk_seconds: int,
) -> tuple[ReadVideoAudioChunkReservation, ...]:
    span = range_end_seconds - range_start_seconds
    if span < _MIN_CHUNK_SECONDS:
        return ()
    chunks: list[ReadVideoAudioChunkReservation] = []
    chunk_index = 0
    while True:
        start = range_start_seconds + chunk_index * chunk_seconds
        if start >= range_end_seconds:
            break
        end = min(range_end_seconds, start + chunk_seconds)
        if (end - start) < _MIN_CHUNK_SECONDS:
            break
        chunks.append(
            ReadVideoAudioChunkReservation(
                chunk_index=chunk_index,
                start_seconds=start,
                end_seconds=end,
            ),
        )
        chunk_index += 1
    return tuple(chunks)


def map_chunk_segments(
    payload: JSONDict,
    *,
    chunk: ReadVideoAudioChunkReservation,
    range_start_seconds: float,
    range_end_seconds: float,
    segment_stride: int,
) -> tuple[str, tuple[ReadVideoAudioSegmentValue, ...]]:
    transcript = payload.get("transcript")
    if not isinstance(transcript, dict):
        return "", ()
    text_value = transcript.get("text")
    text = str(text_value) if text_value is not None else ""
    raw_segments = transcript.get("segments")
    if not isinstance(raw_segments, list):
        return text, ()
    result: list[ReadVideoAudioSegmentValue] = []
    for local_index, item in enumerate(raw_segments):
        if not isinstance(item, dict):
            continue
        seg_start = json_float(item.get("start"), default=0.0) + chunk.start_seconds
        seg_end = json_float(item.get("end"), default=0.0) + chunk.start_seconds
        clamped_start = max(range_start_seconds, min(seg_start, range_end_seconds))
        clamped_end = max(range_start_seconds, min(seg_end, range_end_seconds))
        if clamped_end <= clamped_start:
            continue
        seg_text = str(item.get("text")).strip()
        if not seg_text:
            continue
        segment_index = chunk.chunk_index * segment_stride + local_index
        result.append(
            ReadVideoAudioSegmentValue(
                segment_index=segment_index,
                chunk_index=chunk.chunk_index,
                start_seconds=clamped_start,
                end_seconds=clamped_end,
                text=seg_text,
            ),
        )
    return text, tuple(result)
