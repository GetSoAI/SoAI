"""SoAI - MCP read_video bounded frame and audio page readers [backend/mcp/tools/read_video_page.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.filesystem.open_files import open_binary
from core.read_video.enums import ReadVideoArtifactStatus
from core.serialization.base64_values import encode_base64_ascii
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.read_video.records import (
        ReadVideoAudioChunkRecord,
        ReadVideoFrameRecord,
        ReadVideoJobRecord,
    )
    from core.types.json import JSONDict

__all__ = (
    "ReadVideoAudioPage",
    "ReadVideoFramePage",
    "read_audio_page",
    "read_frame_page",
)


@dataclass(frozen=True, slots=True)
class ReadVideoFramePage:
    frames: tuple[JSONDict, ...]
    total_frames: int
    next_frame_offset: int | None


@dataclass(frozen=True, slots=True)
class ReadVideoAudioPage:
    segments: tuple[JSONDict, ...]
    total_segments: int
    transcript_text: str
    next_segment_offset: int | None


def _next_offset(start_index: int, limit: int, total: int) -> int | None:
    advanced = start_index + limit
    return advanced if advanced < total else None


def _read_frame_bytes(record: ReadVideoFrameRecord) -> bytes:
    if record.artifact_path is None:
        raise MCPToolError(
            -32603,
            f"read_video frame {record.frame_index} is missing its artifact path.",
        )
    try:
        with open_binary(record.artifact_path, mode="rb") as handle:
            return handle.read()
    except OSError as exception:
        raise MCPToolError(
            -32603,
            f"read_video could not read frame {record.frame_index} artifact.",
        ) from exception


def _frame_to_dict(record: ReadVideoFrameRecord) -> JSONDict:
    data = _read_frame_bytes(record)
    return {
        "frame_index": record.frame_index,
        "timestamp_seconds": record.timestamp_seconds,
        "content_type": record.content_type,
        "image_base64": encode_base64_ascii(data),
        "byte_size": record.byte_size,
        "encoded_chars": record.encoded_chars,
        "width": record.width,
        "height": record.height,
        "source_width": record.source_width,
        "source_height": record.source_height,
    }


async def read_frame_page(
    repository: DatabaseReadVideoJobsProtocol,
    job: ReadVideoJobRecord,
    *,
    start_index: int,
    limit: int,
) -> ReadVideoFramePage:
    records = await repository.read_completed_frames(job.job_id, start_index, limit)
    total = await repository.count_completed_frames(job.job_id)
    frames = tuple(_frame_to_dict(record) for record in records)
    return ReadVideoFramePage(
        frames=frames,
        total_frames=total,
        next_frame_offset=_next_offset(start_index, limit, total),
    )


def _segment_to_dict(
    segment_index: int,
    chunk_index: int,
    start: float,
    end: float,
    text: str,
) -> JSONDict:
    return {
        "segment_index": segment_index,
        "chunk_index": chunk_index,
        "start_seconds": start,
        "end_seconds": end,
        "text": text,
    }


def _transcript_text(chunks: tuple[ReadVideoAudioChunkRecord, ...]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        if chunk.status != ReadVideoArtifactStatus.COMPLETED:
            continue
        if chunk.text is None:
            continue
        stripped = chunk.text.strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


async def read_audio_page(
    repository: DatabaseReadVideoJobsProtocol,
    job: ReadVideoJobRecord,
    *,
    start_index: int,
    limit: int,
) -> ReadVideoAudioPage:
    records = await repository.read_audio_segments(job.job_id, start_index, limit)
    total = await repository.count_audio_segments(job.job_id)
    chunks = await repository.read_audio_chunks(job.job_id)
    segments = tuple(
        _segment_to_dict(
            record.segment_index,
            record.chunk_index,
            record.start_seconds,
            record.end_seconds,
            record.text,
        )
        for record in records
    )
    return ReadVideoAudioPage(
        segments=segments,
        total_segments=total,
        transcript_text=_transcript_text(chunks),
        next_segment_offset=_next_offset(start_index, limit, total),
    )
