"""SoAI - MCP utility tool definition: read_video [backend/mcp/tools/utility_tool_definitions/read_video.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_VIDEO
from mcp.tools.utility_tool_definitions.workspace_path_schema import (
    build_workspace_file_path_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_read_video_tool_definitions",)


def _progress_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "stage": {"type": ["string", "null"]},
            "percent_complete": {"type": "number"},
            "frames_done": {"type": "integer"},
            "frames_total_estimate": {"type": ["integer", "null"]},
            "audio_chunks_done": {"type": "integer"},
            "audio_chunks_total_estimate": {"type": ["integer", "null"]},
            "current_timestamp_seconds": {"type": ["number", "null"]},
        },
    }


def _frame_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "frame_index": {"type": "integer"},
            "timestamp_seconds": {"type": "number"},
            "content_type": {"type": "string"},
            "image_base64": {"type": "string"},
            "byte_size": {"type": "integer"},
            "encoded_chars": {"type": "integer"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "source_width": {"type": "integer"},
            "source_height": {"type": "integer"},
        },
    }


def _audio_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "requested": {"type": "boolean"},
            "skipped": {"type": "boolean"},
            "present": {"type": "boolean"},
            "transcript": {"type": "string"},
            "segments": {"type": "array", "items": {"type": "object"}},
        },
    }


def _preview_schema() -> JSONDict:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "video_base64": {"type": "string"},
            "content_type": {"type": "string"},
            "byte_size": {"type": "integer"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "duration_seconds": {"type": "number"},
            "start_seconds": {"type": "number"},
            "includes_audio": {"type": "boolean"},
        },
    }


def build_read_video_tool_definitions() -> dict[str, JSONDict]:
    return {
        "read_video": {
            "title": "Read Video",
            "description": (
                "Read frames and optional audio transcript from a local workspace video. "
                "The call blocks until the selected range is parsed or cancelled."
            ),
            "icons": [build_tool_icon_entry(ICON_VIDEO)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": build_workspace_file_path_schema(
                        description="Path to a video under workspace_path.",
                    ),
                    "frames_per_second": {
                        "type": "number",
                        "minimum": 0.000001,
                        "maximum": 1.0,
                        "default": 1.0,
                    },
                    "include_audio": {"type": "boolean", "default": True},
                    "start_seconds": {"type": "number", "minimum": 0, "default": 0},
                    "end_seconds": {"type": "number", "minimum": 0},
                    "job_id": {"type": ["string", "null"]},
                    "cursor": {"type": ["string", "null"]},
                    "cancel": {"type": "boolean", "default": False},
                },
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "job_id": {"type": "string"},
                    "task_id": {"type": ["string", "null"]},
                    "status": {"type": "string"},
                    "source_path": {"type": "string"},
                    "source_mime_type": {"type": "string"},
                    "source_size_bytes": {"type": "integer"},
                    "duration_seconds": {"type": "number"},
                    "source_width": {"type": "integer"},
                    "source_height": {"type": "integer"},
                    "audio_present": {"type": "boolean"},
                    "range_start_seconds": {"type": "number"},
                    "range_end_seconds": {"type": "number"},
                    "frames_per_second": {"type": "number"},
                    "include_audio": {"type": "boolean"},
                    "progress": _progress_schema(),
                    "frames": {"type": "array", "items": _frame_schema()},
                    "audio": _audio_schema(),
                    "video_preview": _preview_schema(),
                    "next_cursor": {"type": ["string", "null"]},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
