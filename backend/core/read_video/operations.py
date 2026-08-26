"""SoAI - Core read_video request and value dataclasses [backend/core/read_video/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.read_video.enums import ReadVideoLeaseResult
from core.read_video.records import ReadVideoJobRecord

__all__ = (
    "ReadVideoAudioChunkReservation",
    "ReadVideoAudioSegmentValue",
    "ReadVideoFrameCompletion",
    "ReadVideoFrameReservation",
    "ReadVideoLeaseOutcome",
    "ReadVideoLeaseRequest",
    "ReadVideoProgressUpdate",
)


@dataclass(frozen=True, slots=True)
class ReadVideoFrameReservation:
    frame_index: int
    timestamp_seconds: float


@dataclass(frozen=True, slots=True)
class ReadVideoFrameCompletion:
    job_id: str
    frame_index: int
    artifact_path: str
    content_type: str
    byte_size: int
    encoded_chars: int
    width: int
    height: int
    source_width: int
    source_height: int


@dataclass(frozen=True, slots=True)
class ReadVideoAudioChunkReservation:
    chunk_index: int
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, slots=True)
class ReadVideoAudioSegmentValue:
    segment_index: int
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class ReadVideoLeaseRequest:
    job_id: str
    lease_token: str
    lease_owner: str
    lease_expires_at_ms: int
    now_ms: int
    active_task_id: str | None
    active_tool_call_id: str | None


@dataclass(frozen=True, slots=True)
class ReadVideoLeaseOutcome:
    result: ReadVideoLeaseResult
    job: ReadVideoJobRecord | None


@dataclass(frozen=True, slots=True)
class ReadVideoProgressUpdate:
    job_id: str
    lease_token: str
    now_ms: int
    stage: str | None
    percent_complete: float
    frames_done: int
    frames_total_estimate: int | None
    audio_chunks_done: int
    audio_chunks_total_estimate: int | None
    current_timestamp_seconds: float | None
