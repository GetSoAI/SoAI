"""SoAI - Database read_video lease and lifecycle write transactions [backend/database/repositories/users/read_video_lease_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.read_video.enums import ReadVideoJobStatus, ReadVideoLeaseResult
from core.read_video.operations import ReadVideoLeaseOutcome, ReadVideoLeaseRequest
from core.read_video.records import ReadVideoJobRecord
from database.core.query_execution import (
    sync_fetch_changes_count,
    sync_fetch_one_as_dict,
)
from database.repositories.users.read_video_rows import (
    READ_VIDEO_JOB_COLUMNS,
    parse_read_video_job_row,
    serialize_source_signature,
)

__all__ = (
    "sync_acquire_lease",
    "sync_create_job",
    "sync_delete_job",
    "sync_finalize_job",
    "sync_release_lease",
    "sync_renew_lease",
)


def sync_delete_job(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute("DELETE FROM read_video_jobs WHERE job_id = ?", (job_id,))


def sync_create_job(conn: sqlite3.Connection, job: ReadVideoJobRecord) -> bool:
    conn.execute(
        """
        INSERT INTO read_video_jobs (
            job_id, job_key, owner_key, user_id, conversation_id, active_task_id,
            active_tool_call_id, source_path, source_signature, source_size_bytes,
            source_mime_type, duration_seconds, source_width, source_height, audio_present,
            range_start_seconds, range_end_seconds, frames_per_second, include_audio,
            config_signature, status, progress_stage, percent_complete, frames_done,
            frames_total_estimate, audio_chunks_done, audio_chunks_total_estimate,
            current_timestamp_seconds, page_size, lease_token, lease_owner, lease_expires_at_ms,
            error_code, error_message, created_at_ms, updated_at_ms, expires_at_ms
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(job_key) DO NOTHING
        """,
        (
            job.job_id,
            job.job_key,
            job.owner_key,
            job.user_id,
            job.conversation_id,
            job.active_task_id,
            job.active_tool_call_id,
            job.source_path,
            serialize_source_signature(job.source_signature),
            job.source_size_bytes,
            job.source_mime_type,
            job.duration_seconds,
            job.source_width,
            job.source_height,
            1 if job.audio_present else 0,
            job.range_start_seconds,
            job.range_end_seconds,
            job.frames_per_second,
            1 if job.include_audio else 0,
            job.config_signature,
            job.status.value,
            job.progress_stage,
            job.percent_complete,
            job.frames_done,
            job.frames_total_estimate,
            job.audio_chunks_done,
            job.audio_chunks_total_estimate,
            job.current_timestamp_seconds,
            job.page_size,
            job.lease_token,
            job.lease_owner,
            job.lease_expires_at_ms,
            job.error_code,
            job.error_message,
            job.created_at_ms,
            job.updated_at_ms,
            job.expires_at_ms,
        ),
    )
    return sync_fetch_changes_count(conn) > 0


def _select_job(conn: sqlite3.Connection, job_id: str) -> ReadVideoJobRecord | None:
    cursor = conn.execute(
        f"SELECT {READ_VIDEO_JOB_COLUMNS} FROM read_video_jobs WHERE job_id = ?",
        (job_id,),
    )
    row = sync_fetch_one_as_dict(cursor)
    if row is None:
        return None
    return parse_read_video_job_row(row)


def sync_acquire_lease(
    conn: sqlite3.Connection,
    request: ReadVideoLeaseRequest,
) -> ReadVideoLeaseOutcome:
    current = _select_job(conn, request.job_id)
    if current is None:
        return ReadVideoLeaseOutcome(result=ReadVideoLeaseResult.NOT_FOUND, job=None)
    if current.status == ReadVideoJobStatus.COMPLETED:
        return ReadVideoLeaseOutcome(result=ReadVideoLeaseResult.COMPLETED, job=current)
    if (
        current.lease_token is not None
        and current.lease_expires_at_ms is not None
        and current.lease_expires_at_ms >= request.now_ms
        and current.lease_token != request.lease_token
    ):
        return ReadVideoLeaseOutcome(result=ReadVideoLeaseResult.BUSY, job=current)
    conn.execute(
        """
        UPDATE read_video_jobs
        SET lease_token = ?, lease_owner = ?, lease_expires_at_ms = ?, active_task_id = ?,
            active_tool_call_id = ?, status = 'running', updated_at_ms = ?
        WHERE job_id = ?
        """,
        (
            request.lease_token,
            request.lease_owner,
            request.lease_expires_at_ms,
            request.active_task_id,
            request.active_tool_call_id,
            request.now_ms,
            request.job_id,
        ),
    )
    acquired = _select_job(conn, request.job_id)
    return ReadVideoLeaseOutcome(result=ReadVideoLeaseResult.ACQUIRED, job=acquired)


def sync_renew_lease(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    conn.execute(
        """
        UPDATE read_video_jobs
        SET lease_expires_at_ms = ?, updated_at_ms = ?
        WHERE job_id = ? AND lease_token = ? AND lease_expires_at_ms IS NOT NULL
        """,
        (lease_expires_at_ms, now_ms, job_id, lease_token),
    )
    return sync_fetch_changes_count(conn) > 0


def sync_release_lease(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    now_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE read_video_jobs
        SET lease_token = NULL, lease_owner = NULL, lease_expires_at_ms = NULL, updated_at_ms = ?
        WHERE job_id = ? AND lease_token = ?
        """,
        (now_ms, job_id, lease_token),
    )


def _validate_finalize_status(
    status: ReadVideoJobStatus,
    error_code: str | None,
    error_message: str | None,
) -> None:
    if status == ReadVideoJobStatus.FAILED:
        if error_message is None:
            raise ValidationError("read_video failed finalize requires an error_message.")
        return
    if status in (ReadVideoJobStatus.COMPLETED, ReadVideoJobStatus.CANCELLED):
        if error_code is not None or error_message is not None:
            raise ValidationError(
                "read_video completed/cancelled finalize must not carry an error.",
            )
        return
    if status == ReadVideoJobStatus.INTERRUPTED:
        return
    raise ValidationError(f"read_video finalize does not accept status '{status.value}'.")


def sync_finalize_job(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    status: ReadVideoJobStatus,
    error_code: str | None,
    error_message: str | None,
    now_ms: int,
) -> bool:
    _validate_finalize_status(status, error_code, error_message)
    if status == ReadVideoJobStatus.COMPLETED:
        conn.execute(
            """
            UPDATE read_video_jobs
            SET status = ?, error_code = ?, error_message = ?, lease_token = NULL,
                lease_owner = NULL, lease_expires_at_ms = NULL, percent_complete = 100,
                updated_at_ms = ?
            WHERE job_id = ? AND lease_token = ? AND status = 'running'
            """,
            (status.value, error_code, error_message, now_ms, job_id, lease_token),
        )
    else:
        conn.execute(
            """
            UPDATE read_video_jobs
            SET status = ?, error_code = ?, error_message = ?, lease_token = NULL,
                lease_owner = NULL, lease_expires_at_ms = NULL, updated_at_ms = ?
            WHERE job_id = ? AND lease_token = ? AND status = 'running'
            """,
            (status.value, error_code, error_message, now_ms, job_id, lease_token),
        )
    return sync_fetch_changes_count(conn) > 0
