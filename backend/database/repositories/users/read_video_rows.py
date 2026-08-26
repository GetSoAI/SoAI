"""SoAI - Database read_video row parsing and serialization [backend/database/repositories/users/read_video_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.read_video.enums import ReadVideoArtifactStatus, ReadVideoJobStatus
from core.read_video.records import (
    ReadVideoAudioChunkRecord,
    ReadVideoAudioSegmentRecord,
    ReadVideoFrameRecord,
    ReadVideoJobRecord,
    ReadVideoSourceSignature,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.integers import is_strict_int
from database.core.json_codec import safe_json_deserialize
from database.core.sqlite_numbers import (
    coerce_optional_int_from_sqlite_row,
    coerce_optional_str_from_sqlite_row,
    coerce_required_bool_from_sqlite_row,
    coerce_required_float_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from database.core.sqlite_values import SQLiteRow, SQLiteValue

__all__ = (
    "READ_VIDEO_AUDIO_CHUNK_COLUMNS",
    "READ_VIDEO_AUDIO_SEGMENT_COLUMNS",
    "READ_VIDEO_FRAME_COLUMNS",
    "READ_VIDEO_JOB_COLUMNS",
    "parse_read_video_audio_chunk_row",
    "parse_read_video_audio_segment_row",
    "parse_read_video_frame_row",
    "parse_read_video_job_row",
    "serialize_source_signature",
)

READ_VIDEO_JOB_COLUMNS = (
    "job_id, job_key, owner_key, user_id, conversation_id, active_task_id, active_tool_call_id, "
    "source_path, source_signature, source_size_bytes, source_mime_type, duration_seconds, "
    "source_width, source_height, audio_present, range_start_seconds, range_end_seconds, "
    "frames_per_second, include_audio, config_signature, status, progress_stage, percent_complete, "
    "frames_done, frames_total_estimate, audio_chunks_done, audio_chunks_total_estimate, "
    "current_timestamp_seconds, page_size, lease_token, lease_owner, lease_expires_at_ms, "
    "error_code, error_message, created_at_ms, updated_at_ms, expires_at_ms"
)

READ_VIDEO_FRAME_COLUMNS = (
    "job_id, frame_index, timestamp_seconds, artifact_path, content_type, byte_size, "
    "encoded_chars, width, height, source_width, source_height, status, error_message"
)

READ_VIDEO_AUDIO_CHUNK_COLUMNS = (
    "job_id, chunk_index, start_seconds, end_seconds, status, text, error_message"
)

READ_VIDEO_AUDIO_SEGMENT_COLUMNS = (
    "job_id, segment_index, chunk_index, start_seconds, end_seconds, text"
)


def serialize_source_signature(signature: ReadVideoSourceSignature) -> str:
    return serialize_json_compact_stable_strict(
        {
            "dev": signature.dev,
            "inode": signature.inode,
            "mtime_ns": signature.mtime_ns,
            "size_bytes": signature.size_bytes,
        },
    )


def _parse_source_signature(row: SQLiteRow) -> ReadVideoSourceSignature:
    decoded = safe_json_deserialize(row.get("source_signature"), None)
    if not isinstance(decoded, dict):
        raise StateError("read_video job source_signature is invalid.")
    dev = decoded.get("dev")
    inode = decoded.get("inode")
    mtime_ns = decoded.get("mtime_ns")
    size_bytes = decoded.get("size_bytes")
    if not all(
        _is_plain_int(value)
        for value in (
            dev,
            inode,
            mtime_ns,
            size_bytes,
        )
    ):
        raise StateError("read_video job source_signature is invalid.")
    resolved_dev = _require_plain_int(dev)
    resolved_inode = _require_plain_int(inode)
    resolved_mtime_ns = _require_plain_int(mtime_ns)
    resolved_size_bytes = _require_plain_int(size_bytes)
    return ReadVideoSourceSignature(
        dev=resolved_dev,
        inode=resolved_inode,
        mtime_ns=resolved_mtime_ns,
        size_bytes=resolved_size_bytes,
    )


def _parse_job_status(row: SQLiteRow) -> ReadVideoJobStatus:
    value = row.get("status")
    if not isinstance(value, str):
        raise StateError("read_video job status is invalid.")
    return ReadVideoJobStatus(value)


def _parse_artifact_status(value: SQLiteValue) -> ReadVideoArtifactStatus:
    if not isinstance(value, str):
        raise StateError("read_video artifact status is invalid.")
    return ReadVideoArtifactStatus(value)


def parse_read_video_job_row(row: SQLiteRow) -> ReadVideoJobRecord:
    return ReadVideoJobRecord(
        job_id=coerce_required_nonempty_str_from_sqlite_row(row, "job_id"),
        job_key=coerce_required_nonempty_str_from_sqlite_row(row, "job_key"),
        owner_key=coerce_required_nonempty_str_from_sqlite_row(row, "owner_key"),
        user_id=coerce_optional_str_from_sqlite_row(row, "user_id"),
        conversation_id=coerce_optional_str_from_sqlite_row(row, "conversation_id"),
        active_task_id=coerce_optional_str_from_sqlite_row(row, "active_task_id"),
        active_tool_call_id=coerce_optional_str_from_sqlite_row(row, "active_tool_call_id"),
        source_path=coerce_required_nonempty_str_from_sqlite_row(row, "source_path"),
        source_signature=_parse_source_signature(row),
        source_size_bytes=coerce_required_int_from_sqlite_row(row, "source_size_bytes"),
        source_mime_type=coerce_required_nonempty_str_from_sqlite_row(row, "source_mime_type"),
        duration_seconds=coerce_required_float_from_sqlite_row(row, "duration_seconds"),
        source_width=coerce_required_int_from_sqlite_row(row, "source_width"),
        source_height=coerce_required_int_from_sqlite_row(row, "source_height"),
        audio_present=coerce_required_bool_from_sqlite_row(row, "audio_present"),
        range_start_seconds=coerce_required_float_from_sqlite_row(row, "range_start_seconds"),
        range_end_seconds=coerce_required_float_from_sqlite_row(row, "range_end_seconds"),
        frames_per_second=coerce_required_float_from_sqlite_row(row, "frames_per_second"),
        include_audio=coerce_required_bool_from_sqlite_row(row, "include_audio"),
        config_signature=coerce_required_nonempty_str_from_sqlite_row(row, "config_signature"),
        status=_parse_job_status(row),
        progress_stage=coerce_optional_str_from_sqlite_row(row, "progress_stage"),
        percent_complete=coerce_required_float_from_sqlite_row(row, "percent_complete"),
        frames_done=coerce_required_int_from_sqlite_row(row, "frames_done"),
        frames_total_estimate=coerce_optional_int_from_sqlite_row(row, "frames_total_estimate"),
        audio_chunks_done=coerce_required_int_from_sqlite_row(row, "audio_chunks_done"),
        audio_chunks_total_estimate=coerce_optional_int_from_sqlite_row(
            row,
            "audio_chunks_total_estimate",
        ),
        current_timestamp_seconds=_coerce_optional_float(row, "current_timestamp_seconds"),
        page_size=coerce_required_int_from_sqlite_row(row, "page_size"),
        lease_token=coerce_optional_str_from_sqlite_row(row, "lease_token"),
        lease_owner=coerce_optional_str_from_sqlite_row(row, "lease_owner"),
        lease_expires_at_ms=coerce_optional_int_from_sqlite_row(row, "lease_expires_at_ms"),
        error_code=coerce_optional_str_from_sqlite_row(row, "error_code"),
        error_message=coerce_optional_str_from_sqlite_row(row, "error_message"),
        created_at_ms=coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        updated_at_ms=coerce_required_int_from_sqlite_row(row, "updated_at_ms"),
        expires_at_ms=coerce_required_int_from_sqlite_row(row, "expires_at_ms"),
    )


def _coerce_optional_float(row: SQLiteRow, key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    return coerce_required_float_from_sqlite_row(row, key)


def _is_plain_int(value: JSONValue) -> bool:
    return is_strict_int(value)


def _require_plain_int(value: JSONValue) -> int:
    if not is_strict_int(value):
        raise StateError("read_video job source_signature is invalid.")
    return value


def parse_read_video_frame_row(row: SQLiteRow) -> ReadVideoFrameRecord:
    return ReadVideoFrameRecord(
        job_id=coerce_required_nonempty_str_from_sqlite_row(row, "job_id"),
        frame_index=coerce_required_int_from_sqlite_row(row, "frame_index"),
        timestamp_seconds=coerce_required_float_from_sqlite_row(row, "timestamp_seconds"),
        artifact_path=coerce_optional_str_from_sqlite_row(row, "artifact_path"),
        content_type=coerce_optional_str_from_sqlite_row(row, "content_type"),
        byte_size=coerce_optional_int_from_sqlite_row(row, "byte_size"),
        encoded_chars=coerce_optional_int_from_sqlite_row(row, "encoded_chars"),
        width=coerce_optional_int_from_sqlite_row(row, "width"),
        height=coerce_optional_int_from_sqlite_row(row, "height"),
        source_width=coerce_optional_int_from_sqlite_row(row, "source_width"),
        source_height=coerce_optional_int_from_sqlite_row(row, "source_height"),
        status=_parse_artifact_status(row.get("status")),
        error_message=coerce_optional_str_from_sqlite_row(row, "error_message"),
    )


def parse_read_video_audio_chunk_row(row: SQLiteRow) -> ReadVideoAudioChunkRecord:
    return ReadVideoAudioChunkRecord(
        job_id=coerce_required_nonempty_str_from_sqlite_row(row, "job_id"),
        chunk_index=coerce_required_int_from_sqlite_row(row, "chunk_index"),
        start_seconds=coerce_required_float_from_sqlite_row(row, "start_seconds"),
        end_seconds=coerce_required_float_from_sqlite_row(row, "end_seconds"),
        status=_parse_artifact_status(row.get("status")),
        text=coerce_optional_str_from_sqlite_row(row, "text"),
        error_message=coerce_optional_str_from_sqlite_row(row, "error_message"),
    )


def parse_read_video_audio_segment_row(row: SQLiteRow) -> ReadVideoAudioSegmentRecord:
    return ReadVideoAudioSegmentRecord(
        job_id=coerce_required_nonempty_str_from_sqlite_row(row, "job_id"),
        segment_index=coerce_required_int_from_sqlite_row(row, "segment_index"),
        chunk_index=coerce_required_int_from_sqlite_row(row, "chunk_index"),
        start_seconds=coerce_required_float_from_sqlite_row(row, "start_seconds"),
        end_seconds=coerce_required_float_from_sqlite_row(row, "end_seconds"),
        text=_require_segment_text(row),
    )


def _require_segment_text(row: SQLiteRow) -> str:
    value = row.get("text")
    if not isinstance(value, str):
        raise StateError("read_video audio segment text is invalid.")
    return value
