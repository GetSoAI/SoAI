"""SoAI - Database read_video audio artifact write transactions [backend/database/repositories/users/read_video_audio_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.read_video.operations import (
    ReadVideoAudioChunkReservation,
    ReadVideoAudioSegmentValue,
)

__all__ = (
    "sync_complete_audio_chunk",
    "sync_fail_audio_chunk",
    "sync_reserve_audio_chunks",
)


def sync_reserve_audio_chunks(
    conn: sqlite3.Connection,
    job_id: str,
    chunks: tuple[ReadVideoAudioChunkReservation, ...],
) -> None:
    if not chunks:
        return
    conn.executemany(
        """
        INSERT INTO read_video_audio_chunks (job_id, chunk_index, start_seconds, end_seconds, status)
        VALUES (?, ?, ?, ?, 'pending')
        ON CONFLICT(job_id, chunk_index) DO NOTHING
        """,
        [(job_id, chunk.chunk_index, chunk.start_seconds, chunk.end_seconds) for chunk in chunks],
    )


def sync_complete_audio_chunk(
    conn: sqlite3.Connection,
    job_id: str,
    chunk_index: int,
    text: str,
    segments: tuple[ReadVideoAudioSegmentValue, ...],
) -> None:
    conn.execute(
        """
        UPDATE read_video_audio_chunks
        SET status = 'completed', text = ?, error_message = NULL
        WHERE job_id = ? AND chunk_index = ?
        """,
        (text, job_id, chunk_index),
    )
    conn.execute(
        "DELETE FROM read_video_audio_segments WHERE job_id = ? AND chunk_index = ?",
        (job_id, chunk_index),
    )
    if not segments:
        return
    conn.executemany(
        """
        INSERT INTO read_video_audio_segments (
            job_id, segment_index, chunk_index, start_seconds, end_seconds, text
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                job_id,
                segment.segment_index,
                segment.chunk_index,
                segment.start_seconds,
                segment.end_seconds,
                segment.text,
            )
            for segment in segments
        ],
    )


def sync_fail_audio_chunk(
    conn: sqlite3.Connection,
    job_id: str,
    chunk_index: int,
    error_message: str,
) -> None:
    conn.execute(
        """
        UPDATE read_video_audio_chunks
        SET status = 'failed', error_message = ?
        WHERE job_id = ? AND chunk_index = ?
        """,
        (error_message, job_id, chunk_index),
    )
