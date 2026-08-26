"""SoAI - Database read_video progress write transaction [backend/database/repositories/users/read_video_progress_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.read_video.operations import ReadVideoProgressUpdate

__all__ = ("sync_update_progress",)


def sync_update_progress(conn: sqlite3.Connection, progress: ReadVideoProgressUpdate) -> None:
    conn.execute(
        """
        UPDATE read_video_jobs
        SET progress_stage = ?, percent_complete = ?, frames_done = ?, frames_total_estimate = ?,
            audio_chunks_done = ?, audio_chunks_total_estimate = ?, current_timestamp_seconds = ?,
            updated_at_ms = ?
        WHERE job_id = ? AND lease_token = ? AND status = 'running'
        """,
        (
            progress.stage,
            progress.percent_complete,
            progress.frames_done,
            progress.frames_total_estimate,
            progress.audio_chunks_done,
            progress.audio_chunks_total_estimate,
            progress.current_timestamp_seconds,
            progress.now_ms,
            progress.job_id,
            progress.lease_token,
        ),
    )
