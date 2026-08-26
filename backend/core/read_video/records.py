"""SoAI - Core read_video persisted record dataclasses [backend/core/read_video/records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.read_video.enums import ReadVideoArtifactStatus, ReadVideoJobStatus

__all__ = (
    "ReadVideoAudioChunkRecord",
    "ReadVideoAudioSegmentRecord",
    "ReadVideoFrameRecord",
    "ReadVideoJobRecord",
    "ReadVideoSourceSignature",
)


@dataclass(frozen=True, slots=True)
class ReadVideoSourceSignature:
    dev: int
    inode: int
    mtime_ns: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ReadVideoJobRecord:
    job_id: str
    job_key: str
    owner_key: str
    user_id: str | None
    conversation_id: str | None
    active_task_id: str | None
    active_tool_call_id: str | None
    source_path: str
    source_signature: ReadVideoSourceSignature
    source_size_bytes: int
    source_mime_type: str
    duration_seconds: float
    source_width: int
    source_height: int
    audio_present: bool
    range_start_seconds: float
    range_end_seconds: float
    frames_per_second: float
    include_audio: bool
    config_signature: str
    status: ReadVideoJobStatus
    progress_stage: str | None
    percent_complete: float
    frames_done: int
    frames_total_estimate: int | None
    audio_chunks_done: int
    audio_chunks_total_estimate: int | None
    current_timestamp_seconds: float | None
    page_size: int
    lease_token: str | None
    lease_owner: str | None
    lease_expires_at_ms: int | None
    error_code: str | None
    error_message: str | None
    created_at_ms: int
    updated_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class ReadVideoFrameRecord:
    job_id: str
    frame_index: int
    timestamp_seconds: float
    artifact_path: str | None
    content_type: str | None
    byte_size: int | None
    encoded_chars: int | None
    width: int | None
    height: int | None
    source_width: int | None
    source_height: int | None
    status: ReadVideoArtifactStatus
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ReadVideoAudioChunkRecord:
    job_id: str
    chunk_index: int
    start_seconds: float
    end_seconds: float
    status: ReadVideoArtifactStatus
    text: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ReadVideoAudioSegmentRecord:
    job_id: str
    segment_index: int
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str
