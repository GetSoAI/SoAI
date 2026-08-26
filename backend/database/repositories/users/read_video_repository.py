"""SoAI - Database read_video durable job repository operations [backend/database/repositories/users/read_video_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseCoreProtocol
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
from database.repositories.users.read_video_audio_ops import (
    sync_complete_audio_chunk,
    sync_fail_audio_chunk,
    sync_reserve_audio_chunks,
)
from database.repositories.users.read_video_frame_ops import (
    sync_complete_frame,
    sync_fail_frame,
    sync_reserve_frames,
)
from database.repositories.users.read_video_lease_ops import (
    sync_acquire_lease,
    sync_create_job,
    sync_delete_job,
    sync_finalize_job,
    sync_release_lease,
    sync_renew_lease,
)
from database.repositories.users.read_video_progress_ops import sync_update_progress
from database.repositories.users.read_video_reads import (
    read_audio_chunks,
    read_audio_segments,
    read_completed_chunk_indices,
    read_completed_frame_indices,
    read_completed_frames,
    read_count_audio_segments,
    read_count_completed_frames,
    read_count_running_jobs,
    read_expired_jobs,
    read_get_job_by_id,
    read_get_job_by_key,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseReadVideoJobs",)


class DatabaseReadVideoJobs:
    core: DatabaseCoreProtocol

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def create_job(self, job: ReadVideoJobRecord) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_create_job,
            job,
        )

    async def get_job_by_id(self, job_id: str) -> ReadVideoJobRecord | None:
        return await self.core.reader.execute_read(read_get_job_by_id, job_id)

    async def get_job_by_key(self, job_key: str) -> ReadVideoJobRecord | None:
        return await self.core.reader.execute_read(read_get_job_by_key, job_key)

    async def count_running_jobs(self, owner_key: str, now_ms: int) -> int:
        return await self.core.reader.execute_read(read_count_running_jobs, owner_key, now_ms)

    async def acquire_lease(self, request: ReadVideoLeaseRequest) -> ReadVideoLeaseOutcome:
        return await self.core.writer.queue_write_operation(
            sync_acquire_lease,
            request,
        )

    async def renew_lease(
        self,
        job_id: str,
        lease_token: str,
        lease_expires_at_ms: int,
        now_ms: int,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_renew_lease,
            job_id,
            lease_token,
            lease_expires_at_ms,
            now_ms,
        )

    async def release_lease(self, job_id: str, lease_token: str, now_ms: int) -> None:
        await self.core.writer.queue_write_operation(
            sync_release_lease,
            job_id,
            lease_token,
            now_ms,
        )

    async def update_progress(self, progress: ReadVideoProgressUpdate) -> None:
        await self.core.writer.queue_write_operation(
            sync_update_progress,
            progress,
        )

    async def finalize_job(
        self,
        job_id: str,
        lease_token: str,
        status: ReadVideoJobStatus,
        error_code: str | None,
        error_message: str | None,
        now_ms: int,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_finalize_job,
            job_id,
            lease_token,
            status,
            error_code,
            error_message,
            now_ms,
        )

    async def reserve_frames(
        self,
        job_id: str,
        frames: tuple[ReadVideoFrameReservation, ...],
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_reserve_frames,
            job_id,
            frames,
        )

    async def complete_frame(self, completion: ReadVideoFrameCompletion) -> None:
        await self.core.writer.queue_write_operation(
            sync_complete_frame,
            completion,
        )

    async def fail_frame(self, job_id: str, frame_index: int, error_message: str) -> None:
        await self.core.writer.queue_write_operation(
            sync_fail_frame,
            job_id,
            frame_index,
            error_message,
        )

    async def get_completed_frame_indices(self, job_id: str) -> frozenset[int]:
        return await self.core.reader.execute_read(read_completed_frame_indices, job_id)

    async def read_completed_frames(
        self,
        job_id: str,
        start_index: int,
        limit: int,
    ) -> tuple[ReadVideoFrameRecord, ...]:
        return await self.core.reader.execute_read(
            read_completed_frames,
            job_id,
            start_index,
            limit,
        )

    async def count_completed_frames(self, job_id: str) -> int:
        return await self.core.reader.execute_read(read_count_completed_frames, job_id)

    async def reserve_audio_chunks(
        self,
        job_id: str,
        chunks: tuple[ReadVideoAudioChunkReservation, ...],
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_reserve_audio_chunks,
            job_id,
            chunks,
        )

    async def complete_audio_chunk(
        self,
        job_id: str,
        chunk_index: int,
        text: str,
        segments: tuple[ReadVideoAudioSegmentValue, ...],
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_complete_audio_chunk,
            job_id,
            chunk_index,
            text,
            segments,
        )

    async def fail_audio_chunk(self, job_id: str, chunk_index: int, error_message: str) -> None:
        await self.core.writer.queue_write_operation(
            sync_fail_audio_chunk,
            job_id,
            chunk_index,
            error_message,
        )

    async def get_completed_chunk_indices(self, job_id: str) -> frozenset[int]:
        return await self.core.reader.execute_read(read_completed_chunk_indices, job_id)

    async def read_audio_chunks(self, job_id: str) -> tuple[ReadVideoAudioChunkRecord, ...]:
        return await self.core.reader.execute_read(read_audio_chunks, job_id)

    async def read_audio_segments(
        self,
        job_id: str,
        start_index: int,
        limit: int,
    ) -> tuple[ReadVideoAudioSegmentRecord, ...]:
        return await self.core.reader.execute_read(read_audio_segments, job_id, start_index, limit)

    async def count_audio_segments(self, job_id: str) -> int:
        return await self.core.reader.execute_read(read_count_audio_segments, job_id)

    async def list_expired_jobs(self, now_ms: int, limit: int) -> tuple[ReadVideoJobRecord, ...]:
        return await self.core.reader.execute_read(read_expired_jobs, now_ms, limit)

    async def delete_job(self, job_id: str) -> None:
        await self.core.writer.queue_write_operation(sync_delete_job, job_id)
