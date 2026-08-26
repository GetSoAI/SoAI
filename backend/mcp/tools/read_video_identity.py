"""SoAI - Deterministic read_video job identity helpers [backend/mcp/tools/read_video_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from core.read_video.records import ReadVideoSourceSignature
from core.serialization.json import serialize_json_compact_stable_strict
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.read_video_config import ReadVideoConfig

__all__ = (
    "compute_config_signature",
    "compute_job_key",
    "compute_source_signature",
)


def compute_source_signature(resolved_path: str) -> ReadVideoSourceSignature:
    try:
        stat = os.stat(resolved_path)
    except OSError as exception:
        raise MCPToolError(-32602, f"read_video cannot stat source: {resolved_path}") from exception
    return ReadVideoSourceSignature(
        dev=stat.st_dev,
        inode=stat.st_ino,
        mtime_ns=stat.st_mtime_ns,
        size_bytes=stat.st_size,
    )


def compute_config_signature(config: ReadVideoConfig) -> str:
    mapping: JSONDict = {
        "version": "v1",
        "max_frame_pixels": config.max_frame_pixels,
        "jpeg_quality": config.jpeg_quality,
        "audio_chunk_seconds": config.audio_chunk_seconds,
        "whisper_model": config.whisper_model,
    }
    payload = serialize_json_compact_stable_strict(mapping).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_job_key(
    *,
    config_signature: str,
    resolved_path: str,
    source_signature: ReadVideoSourceSignature,
    range_start_seconds: float,
    range_end_seconds: float,
    frames_per_second: float,
    include_audio: bool,
) -> str:
    start_ms = round(range_start_seconds * 1000)
    end_ms = round(range_end_seconds * 1000)
    fps = round(float(frames_per_second), 4)
    mapping: JSONDict = {
        "version": "v1",
        "config_signature": config_signature,
        "resolved_path": resolved_path,
        "source": {
            "dev": source_signature.dev,
            "inode": source_signature.inode,
            "mtime_ns": source_signature.mtime_ns,
            "size_bytes": source_signature.size_bytes,
        },
        "range_start_ms": start_ms,
        "range_end_ms": end_ms,
        "frames_per_second": fps,
        "include_audio": bool(include_audio),
    }
    payload = serialize_json_compact_stable_strict(mapping).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
