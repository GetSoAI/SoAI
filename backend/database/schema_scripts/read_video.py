"""SoAI - Database schema: read_video jobs and artifacts [backend/database/schema_scripts/read_video.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_read_video_schema",)


def _build_read_video_jobs_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS read_video_jobs (
            job_id TEXT PRIMARY KEY,
            job_key TEXT NOT NULL UNIQUE,
            owner_key TEXT NOT NULL CHECK(length(trim(owner_key)) > 0),
            user_id TEXT,
            conversation_id TEXT,
            active_task_id TEXT,
            active_tool_call_id TEXT,
            source_path TEXT NOT NULL CHECK(length(trim(source_path)) > 0),
            source_signature TEXT NOT NULL CHECK(json_valid(source_signature)),
            source_size_bytes INTEGER NOT NULL CHECK(source_size_bytes >= 0),
            source_mime_type TEXT NOT NULL,
            duration_seconds REAL NOT NULL CHECK(duration_seconds > 0),
            source_width INTEGER NOT NULL CHECK(source_width > 0),
            source_height INTEGER NOT NULL CHECK(source_height > 0),
            audio_present INTEGER NOT NULL CHECK(audio_present IN (0, 1)),
            range_start_seconds REAL NOT NULL CHECK(range_start_seconds >= 0),
            range_end_seconds REAL NOT NULL CHECK(range_end_seconds > range_start_seconds),
            frames_per_second REAL NOT NULL CHECK(frames_per_second > 0),
            include_audio INTEGER NOT NULL CHECK(include_audio IN (0, 1)),
            config_signature TEXT NOT NULL CHECK(length(trim(config_signature)) > 0),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'cancelled', 'interrupted', 'failed')),
            progress_stage TEXT,
            percent_complete REAL NOT NULL DEFAULT 0 CHECK(percent_complete >= 0 AND percent_complete <= 100),
            frames_done INTEGER NOT NULL DEFAULT 0 CHECK(frames_done >= 0),
            frames_total_estimate INTEGER CHECK(frames_total_estimate IS NULL OR frames_total_estimate >= 0),
            audio_chunks_done INTEGER NOT NULL DEFAULT 0 CHECK(audio_chunks_done >= 0),
            audio_chunks_total_estimate INTEGER CHECK(audio_chunks_total_estimate IS NULL OR audio_chunks_total_estimate >= 0),
            current_timestamp_seconds REAL CHECK(current_timestamp_seconds IS NULL OR current_timestamp_seconds >= 0),
            page_size INTEGER NOT NULL CHECK(page_size > 0),
            lease_token TEXT,
            lease_owner TEXT,
            lease_expires_at_ms INTEGER CHECK(lease_expires_at_ms IS NULL OR lease_expires_at_ms >= {EPOCH_MS_MIN}),
            error_code TEXT,
            error_message TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_read_video_jobs_owner_status ON read_video_jobs(owner_key, status);
        CREATE INDEX IF NOT EXISTS idx_read_video_jobs_status_expires ON read_video_jobs(status, expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_read_video_jobs_lease_expires ON read_video_jobs(lease_expires_at_ms);
        """


def _build_read_video_children_sql() -> str:
    return """
        CREATE TABLE IF NOT EXISTS read_video_frames (
            job_id TEXT NOT NULL,
            frame_index INTEGER NOT NULL CHECK(frame_index >= 0),
            timestamp_seconds REAL NOT NULL CHECK(timestamp_seconds >= 0),
            artifact_path TEXT,
            content_type TEXT,
            byte_size INTEGER CHECK(byte_size IS NULL OR byte_size >= 0),
            encoded_chars INTEGER CHECK(encoded_chars IS NULL OR encoded_chars >= 0),
            width INTEGER CHECK(width IS NULL OR width > 0),
            height INTEGER CHECK(height IS NULL OR height > 0),
            source_width INTEGER CHECK(source_width IS NULL OR source_width > 0),
            source_height INTEGER CHECK(source_height IS NULL OR source_height > 0),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'failed')),
            error_message TEXT,
            CHECK(status != 'completed' OR (artifact_path IS NOT NULL AND content_type IS NOT NULL AND byte_size IS NOT NULL)),
            PRIMARY KEY(job_id, frame_index),
            FOREIGN KEY(job_id) REFERENCES read_video_jobs(job_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_read_video_frames_job_status ON read_video_frames(job_id, status, frame_index);
        CREATE TABLE IF NOT EXISTS read_video_audio_chunks (
            job_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
            start_seconds REAL NOT NULL CHECK(start_seconds >= 0),
            end_seconds REAL NOT NULL CHECK(end_seconds > start_seconds),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'failed')),
            text TEXT,
            error_message TEXT,
            PRIMARY KEY(job_id, chunk_index),
            FOREIGN KEY(job_id) REFERENCES read_video_jobs(job_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_read_video_audio_chunks_job_status ON read_video_audio_chunks(job_id, status, chunk_index);
        CREATE TABLE IF NOT EXISTS read_video_audio_segments (
            job_id TEXT NOT NULL,
            segment_index INTEGER NOT NULL CHECK(segment_index >= 0),
            chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
            start_seconds REAL NOT NULL CHECK(start_seconds >= 0),
            end_seconds REAL NOT NULL CHECK(end_seconds >= start_seconds),
            text TEXT NOT NULL,
            PRIMARY KEY(job_id, segment_index),
            FOREIGN KEY(job_id) REFERENCES read_video_jobs(job_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_read_video_audio_segments_job_chunk ON read_video_audio_segments(job_id, chunk_index, segment_index);
        """


def apply_read_video_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_read_video_jobs_sql())
    execute_sql_script(conn, _build_read_video_children_sql())
