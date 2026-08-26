"""SoAI - Database read_video frame artifact write transactions [backend/database/repositories/users/read_video_frame_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.read_video.operations import (
    ReadVideoFrameCompletion,
    ReadVideoFrameReservation,
)

__all__ = (
    "sync_complete_frame",
    "sync_fail_frame",
    "sync_reserve_frames",
)


def sync_reserve_frames(
    conn: sqlite3.Connection,
    job_id: str,
    frames: tuple[ReadVideoFrameReservation, ...],
) -> None:
    if not frames:
        return
    conn.executemany(
        """
        INSERT INTO read_video_frames (job_id, frame_index, timestamp_seconds, status)
        VALUES (?, ?, ?, 'pending')
        ON CONFLICT(job_id, frame_index) DO NOTHING
        """,
        [(job_id, frame.frame_index, frame.timestamp_seconds) for frame in frames],
    )


def sync_complete_frame(conn: sqlite3.Connection, completion: ReadVideoFrameCompletion) -> None:
    conn.execute(
        """
        UPDATE read_video_frames
        SET status = 'completed', artifact_path = ?, content_type = ?, byte_size = ?,
            encoded_chars = ?, width = ?, height = ?, source_width = ?, source_height = ?,
            error_message = NULL
        WHERE job_id = ? AND frame_index = ?
        """,
        (
            completion.artifact_path,
            completion.content_type,
            completion.byte_size,
            completion.encoded_chars,
            completion.width,
            completion.height,
            completion.source_width,
            completion.source_height,
            completion.job_id,
            completion.frame_index,
        ),
    )


def sync_fail_frame(
    conn: sqlite3.Connection,
    job_id: str,
    frame_index: int,
    error_message: str,
) -> None:
    conn.execute(
        """
        UPDATE read_video_frames
        SET status = 'failed', error_message = ?
        WHERE job_id = ? AND frame_index = ?
        """,
        (error_message, job_id, frame_index),
    )
