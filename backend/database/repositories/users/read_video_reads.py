"""SoAI - Database read_video async read operations [backend/database/repositories/users/read_video_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.read_video.records import (
    ReadVideoAudioChunkRecord,
    ReadVideoAudioSegmentRecord,
    ReadVideoFrameRecord,
    ReadVideoJobRecord,
)
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.read_video_rows import (
    READ_VIDEO_AUDIO_CHUNK_COLUMNS,
    READ_VIDEO_AUDIO_SEGMENT_COLUMNS,
    READ_VIDEO_FRAME_COLUMNS,
    READ_VIDEO_JOB_COLUMNS,
    parse_read_video_audio_chunk_row,
    parse_read_video_audio_segment_row,
    parse_read_video_frame_row,
    parse_read_video_job_row,
)

__all__ = (
    "read_audio_chunks",
    "read_audio_segments",
    "read_completed_chunk_indices",
    "read_completed_frame_indices",
    "read_completed_frames",
    "read_count_audio_segments",
    "read_count_completed_frames",
    "read_count_running_jobs",
    "read_expired_jobs",
    "read_get_job_by_id",
    "read_get_job_by_key",
)


async def read_get_job_by_id(
    database: aiosqlite.Connection,
    job_id: str,
) -> ReadVideoJobRecord | None:
    row = await query_one_to_dict(
        database,
        f"SELECT {READ_VIDEO_JOB_COLUMNS} FROM read_video_jobs WHERE job_id = ?",
        (job_id,),
    )
    return parse_read_video_job_row(row) if row is not None else None


async def read_get_job_by_key(
    database: aiosqlite.Connection,
    job_key: str,
) -> ReadVideoJobRecord | None:
    row = await query_one_to_dict(
        database,
        f"SELECT {READ_VIDEO_JOB_COLUMNS} FROM read_video_jobs WHERE job_key = ?",
        (job_key,),
    )
    return parse_read_video_job_row(row) if row is not None else None


async def read_count_running_jobs(
    database: aiosqlite.Connection,
    owner_key: str,
    now_ms: int,
) -> int:
    row = await query_one_to_dict(
        database,
        """
        SELECT COUNT(*) AS count FROM read_video_jobs
        WHERE owner_key = ? AND status = 'running'
          AND lease_token IS NOT NULL AND lease_expires_at_ms >= ?
        """,
        (owner_key, now_ms),
    )
    value = row.get("count") if row is not None else None
    return value if isinstance(value, int) else 0


async def read_completed_frame_indices(
    database: aiosqlite.Connection,
    job_id: str,
) -> frozenset[int]:
    rows = await query_to_dicts(
        database,
        "SELECT frame_index FROM read_video_frames WHERE job_id = ? AND status = 'completed'",
        (job_id,),
    )
    return frozenset(value for row in rows if isinstance((value := row.get("frame_index")), int))


async def read_completed_frames(
    database: aiosqlite.Connection,
    job_id: str,
    start_index: int,
    limit: int,
) -> tuple[ReadVideoFrameRecord, ...]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {READ_VIDEO_FRAME_COLUMNS} FROM read_video_frames
        WHERE job_id = ? AND status = 'completed'
        ORDER BY frame_index LIMIT ? OFFSET ?
        """,
        (job_id, limit, start_index),
    )
    return tuple(parse_read_video_frame_row(row) for row in rows)


async def read_count_completed_frames(database: aiosqlite.Connection, job_id: str) -> int:
    row = await query_one_to_dict(
        database,
        "SELECT COUNT(*) AS count FROM read_video_frames WHERE job_id = ? AND status = 'completed'",
        (job_id,),
    )
    value = row.get("count") if row is not None else None
    return value if isinstance(value, int) else 0


async def read_completed_chunk_indices(
    database: aiosqlite.Connection,
    job_id: str,
) -> frozenset[int]:
    rows = await query_to_dicts(
        database,
        "SELECT chunk_index FROM read_video_audio_chunks WHERE job_id = ? AND status = 'completed'",
        (job_id,),
    )
    return frozenset(value for row in rows if isinstance((value := row.get("chunk_index")), int))


async def read_audio_chunks(
    database: aiosqlite.Connection,
    job_id: str,
) -> tuple[ReadVideoAudioChunkRecord, ...]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {READ_VIDEO_AUDIO_CHUNK_COLUMNS} FROM read_video_audio_chunks
        WHERE job_id = ? ORDER BY chunk_index
        """,
        (job_id,),
    )
    return tuple(parse_read_video_audio_chunk_row(row) for row in rows)


async def read_audio_segments(
    database: aiosqlite.Connection,
    job_id: str,
    start_index: int,
    limit: int,
) -> tuple[ReadVideoAudioSegmentRecord, ...]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {READ_VIDEO_AUDIO_SEGMENT_COLUMNS} FROM read_video_audio_segments
        WHERE job_id = ? ORDER BY segment_index LIMIT ? OFFSET ?
        """,
        (job_id, limit, start_index),
    )
    return tuple(parse_read_video_audio_segment_row(row) for row in rows)


async def read_count_audio_segments(database: aiosqlite.Connection, job_id: str) -> int:
    row = await query_one_to_dict(
        database,
        "SELECT COUNT(*) AS count FROM read_video_audio_segments WHERE job_id = ?",
        (job_id,),
    )
    value = row.get("count") if row is not None else None
    return value if isinstance(value, int) else 0


async def read_expired_jobs(
    database: aiosqlite.Connection,
    now_ms: int,
    limit: int,
) -> tuple[ReadVideoJobRecord, ...]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {READ_VIDEO_JOB_COLUMNS} FROM read_video_jobs
        WHERE expires_at_ms < ? ORDER BY expires_at_ms LIMIT ?
        """,
        (now_ms, limit),
    )
    return tuple(parse_read_video_job_row(row) for row in rows)
