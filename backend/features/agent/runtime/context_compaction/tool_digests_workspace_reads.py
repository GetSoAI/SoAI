"""SoAI - Workspace read tool digests for compaction [backend/features/agent/runtime/context_compaction/tool_digests_workspace_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.context_compaction.tool_digests_workspace_formatting import (
    coerce_bool,
    coerce_int,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.internal_protocols import (
        TruncateLineProtocol,
    )

__all__ = ("digest_workspace_read_tool_exchange",)


def digest_workspace_read_tool_exchange(
    tool_name: str,
    tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str] | None:
    if tool_name == "read_document":
        return _digest_read_document(tool_arguments, tool_result, truncate_line=truncate_line)
    if tool_name == "read_file":
        return _digest_read_file(tool_arguments, tool_result, truncate_line=truncate_line)
    if tool_name == "read_image":
        return _digest_read_image(tool_result, truncate_line=truncate_line)
    if tool_name == "read_video":
        return _digest_read_video(tool_result, truncate_line=truncate_line)
    return None


def _digest_read_document(
    tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str]:
    offset_chars = coerce_int(tool_result.get("offset_chars"))
    truncated = coerce_bool(tool_result.get("truncated"))
    detected_type = coerce_optional_trimmed_str(tool_result.get("detected_type"))
    parser_used = coerce_optional_trimmed_str(tool_result.get("parser_used"))
    doc_parts: list[str] = []
    if tool_arguments:
        arg_path = coerce_optional_trimmed_str(tool_arguments.get("file_path"))
        if arg_path:
            doc_parts.append(f"path={truncate_line(arg_path, max_chars=120)}")
    if offset_chars is not None:
        doc_parts.append(f"offset_chars={offset_chars}")
    if truncated is not None:
        doc_parts.append(f"truncated={'yes' if truncated else 'no'}")
    if detected_type:
        doc_parts.append(f"type={truncate_line(detected_type, max_chars=80)}")
    if parser_used:
        doc_parts.append(f"parser={truncate_line(parser_used, max_chars=80)}")
    return [f"read_document: {'; '.join(doc_parts)}"] if doc_parts else []


def _digest_read_file(
    tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str]:
    file_path = coerce_optional_trimmed_str(tool_result.get("path"))
    mode = coerce_optional_trimmed_str(tool_result.get("mode"))
    render = (
        coerce_optional_trimmed_str(tool_arguments.get("render"))
        if tool_arguments is not None
        else None
    )
    offset = coerce_int(tool_result.get("offset"))
    limit = coerce_int(tool_result.get("limit"))
    total_lines = coerce_int(tool_result.get("total_lines"))
    returned_lines = coerce_int(tool_result.get("returned_lines"))
    start_line = coerce_int(tool_result.get("start_line"))
    end_line = coerce_int(tool_result.get("end_line"))
    next_offset = coerce_int(tool_result.get("next_offset"))
    truncation_reason = coerce_optional_trimmed_str(tool_result.get("truncation_reason"))
    serialized_response_chars = coerce_int(tool_result.get("serialized_response_chars"))
    max_serialized_response_chars = coerce_int(tool_result.get("max_serialized_response_chars"))
    truncated = coerce_bool(tool_result.get("truncated"))
    content_truncated = coerce_bool(tool_result.get("content_truncated"))
    content_omitted = coerce_bool(tool_result.get("content_omitted"))
    content_omitted_reason = coerce_optional_trimmed_str(
        tool_result.get("content_omitted_reason"),
    )
    size_bytes = coerce_int(tool_result.get("size_bytes"))
    max_size_bytes = coerce_int(tool_result.get("max_size_bytes"))
    read_parts: list[str] = []
    if file_path:
        read_parts.append(f"path={truncate_line(file_path, max_chars=120)}")
    if mode:
        read_parts.append(f"mode={mode}")
    if render:
        read_parts.append(f"render={render}")
    if offset is not None and limit is not None:
        read_parts.append(f"slice={offset}+{limit}")
    if start_line is not None and end_line is not None:
        read_parts.append(f"returned_range={start_line}-{end_line}")
    if returned_lines is not None:
        read_parts.append(f"returned_lines={returned_lines}")
    if total_lines is not None:
        read_parts.append(f"total_lines={total_lines}")
    if next_offset is not None:
        read_parts.append(f"next_offset={next_offset}")
    if truncated is not None:
        read_parts.append(f"truncated={'yes' if truncated else 'no'}")
    if content_truncated is not None:
        read_parts.append(f"content_truncated={'yes' if content_truncated else 'no'}")
    if content_omitted is not None:
        read_parts.append(f"content_omitted={'yes' if content_omitted else 'no'}")
    if content_omitted_reason:
        read_parts.append(f"content_omitted_reason={content_omitted_reason}")
    if truncation_reason:
        read_parts.append(f"truncation_reason={truncation_reason}")
    if size_bytes is not None:
        read_parts.append(f"size_bytes={size_bytes}")
    if max_size_bytes is not None:
        read_parts.append(f"max_size_bytes={max_size_bytes}")
    if serialized_response_chars is not None and max_serialized_response_chars is not None:
        read_parts.append(
            f"serialized_chars={serialized_response_chars}/{max_serialized_response_chars}",
        )
    if not read_parts and tool_arguments:
        arg_path = coerce_optional_trimmed_str(tool_arguments.get("file_path"))
        if arg_path:
            read_parts.append(f"path={truncate_line(arg_path, max_chars=120)}")
    return [f"read_file: {'; '.join(read_parts)}"] if read_parts else []


def _digest_read_image(
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str]:
    file_path = coerce_optional_trimmed_str(tool_result.get("path"))
    content_type = coerce_optional_trimmed_str(tool_result.get("content_type"))
    width = coerce_int(tool_result.get("width"))
    height = coerce_int(tool_result.get("height"))
    source_size = coerce_int(tool_result.get("source_size_bytes"))
    image_parts: list[str] = []
    if file_path:
        image_parts.append(f"path={truncate_line(file_path, max_chars=120)}")
    if content_type:
        image_parts.append(f"content_type={truncate_line(content_type, max_chars=80)}")
    if width is not None and height is not None:
        image_parts.append(f"size={width}x{height}")
    if source_size is not None:
        image_parts.append(f"source_bytes={source_size}")
    return [f"read_image: {'; '.join(image_parts)}"] if image_parts else []


def _digest_read_video(
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str]:
    source_path = coerce_optional_trimmed_str(tool_result.get("source_path"))
    status = coerce_optional_trimmed_str(tool_result.get("status"))
    frames_per_second = tool_result.get("frames_per_second")
    next_cursor = coerce_optional_trimmed_str(tool_result.get("next_cursor"))
    frames_value = tool_result.get("frames")
    frame_count = len(frames_value) if isinstance(frames_value, list) else None
    video_parts: list[str] = []
    if source_path:
        video_parts.append(f"path={truncate_line(source_path, max_chars=120)}")
    if status:
        video_parts.append(f"status={status}")
    if isinstance(frames_per_second, int | float) and not isinstance(frames_per_second, bool):
        video_parts.append(f"fps={frames_per_second}")
    if frame_count is not None:
        video_parts.append(f"frames={frame_count}")
    if next_cursor:
        video_parts.append("next_cursor=yes")
    return [f"read_video: {'; '.join(video_parts)}"] if video_parts else []
