"""SoAI - Core read_video durable jobs database protocol [backend/core/read_video/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.read_video.enums import ReadVideoJobStatus
from core.read_video.operations import (
    ReadVideoAudioChunkReservation,
    ReadVideoAudioSegmentValue,
    ReadVideoFrameCompletion,
    ReadVideoFrameReservation,
    ReadVideoLeaseOutcome,
    ReadVideoLeaseRequest,
    ReadVideoProgressUpdate,
)
from core.read_video.records import (
    ReadVideoAudioChunkRecord,
    ReadVideoAudioSegmentRecord,
    ReadVideoFrameRecord,
    ReadVideoJobRecord,
)

__all__ = ("DatabaseReadVideoJobsProtocol",)


class DatabaseReadVideoJobsProtocol(Protocol):
    async def create_job(self, job: ReadVideoJobRecord) -> bool: ...

    async def get_job_by_id(self, job_id: str) -> ReadVideoJobRecord | None: ...

    async def get_job_by_key(self, job_key: str) -> ReadVideoJobRecord | None: ...

    async def count_running_jobs(self, owner_key: str, now_ms: int) -> int: ...

    async def acquire_lease(self, request: ReadVideoLeaseRequest) -> ReadVideoLeaseOutcome: ...

    async def renew_lease(
        self,
        job_id: str,
        lease_token: str,
        lease_expires_at_ms: int,
        now_ms: int,
    ) -> bool: ...

    async def release_lease(self, job_id: str, lease_token: str, now_ms: int) -> None: ...

    async def update_progress(self, progress: ReadVideoProgressUpdate) -> None: ...

    async def finalize_job(
        self,
        job_id: str,
        lease_token: str,
        status: ReadVideoJobStatus,
        error_code: str | None,
        error_message: str | None,
        now_ms: int,
    ) -> bool: ...

    async def reserve_frames(
        self,
        job_id: str,
        frames: tuple[ReadVideoFrameReservation, ...],
    ) -> None: ...

    async def complete_frame(self, completion: ReadVideoFrameCompletion) -> None: ...

    async def fail_frame(self, job_id: str, frame_index: int, error_message: str) -> None: ...

    async def get_completed_frame_indices(self, job_id: str) -> frozenset[int]: ...

    async def read_completed_frames(
        self,
        job_id: str,
        start_index: int,
        limit: int,
    ) -> tuple[ReadVideoFrameRecord, ...]: ...

    async def count_completed_frames(self, job_id: str) -> int: ...

    async def reserve_audio_chunks(
        self,
        job_id: str,
        chunks: tuple[ReadVideoAudioChunkReservation, ...],
    ) -> None: ...

    async def complete_audio_chunk(
        self,
        job_id: str,
        chunk_index: int,
        text: str,
        segments: tuple[ReadVideoAudioSegmentValue, ...],
    ) -> None: ...

    async def fail_audio_chunk(self, job_id: str, chunk_index: int, error_message: str) -> None: ...

    async def get_completed_chunk_indices(self, job_id: str) -> frozenset[int]: ...

    async def read_audio_chunks(self, job_id: str) -> tuple[ReadVideoAudioChunkRecord, ...]: ...

    async def read_audio_segments(
        self,
        job_id: str,
        start_index: int,
        limit: int,
    ) -> tuple[ReadVideoAudioSegmentRecord, ...]: ...

    async def count_audio_segments(self, job_id: str) -> int: ...

    async def list_expired_jobs(
        self,
        now_ms: int,
        limit: int,
    ) -> tuple[ReadVideoJobRecord, ...]: ...

    async def delete_job(self, job_id: str) -> None: ...
