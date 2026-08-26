"""SoAI - Timeline tool-result truncation helpers [backend/core/assistant_timeline/tool_result_truncation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONValue

__all__ = (
    "TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS",
    "truncate_tool_result_payload_for_timeline",
)

TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS: int = 32_768
TIMELINE_TOOL_RESULT_PREVIEW_MAX_CHARS: int = 65_536
_PREVIEW_STRING_MAX_CHARS = 4_096
_PREVIEW_MAX_DEPTH = 8
_PREVIEW_MAX_MAPPING_KEYS = 48
_PREVIEW_MAX_SEQUENCE_ITEMS = 24
_BINARY_FIELD_SUFFIX = "_base64"
_TRUNCATION_MARKERS = (
    ("is_truncated", True),
    ("omitted", True),
)
_PREFERRED_SUMMARY_FIELDS = (
    "id",
    "call_id",
    "tool_name",
    "name",
    "status",
    "error",
    "error_message",
    "duration_ms",
    "started_at_ms",
    "completed_at_ms",
    "sequence_index",
    "content_index_before",
    "thinking_index_before",
    "collapsed",
    "url",
    "title",
    "mime_type",
    "content_type",
    "image_url",
    "thumbnail_url",
    "screenshot_url",
    "screenshot_path",
)
_MEDIA_MARKER_FIELDS = (
    "content_type",
    "mime_type",
    "byte_size",
    "size_bytes",
    "width",
    "height",
    "duration_seconds",
    "start_seconds",
    "includes_audio",
    "image_base64_omitted",
    "image_base64_total_chars",
    "image_base64_omission_reason",
    "image_base64_is_truncated",
    "video_base64_omitted",
    "video_base64_total_chars",
    "video_base64_omission_reason",
    "video_base64_is_truncated",
    "screenshot_url",
    "screenshot_path",
    "image_url",
    "thumbnail_url",
)
_MEDIA_CONTAINER_FIELDS = (
    "tool",
    "result",
    "screenshot",
    "image",
    "media",
    "preview",
    "video_preview",
)
_MEDIA_MARKER_MAX_DEPTH = 4


def _build_truncated_string_record(field_name: str, value: str) -> dict[str, JSONValue]:
    inline_max_chars = min(
        TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS,
        _PREVIEW_STRING_MAX_CHARS,
    )
    truncated_value = value[:inline_max_chars]
    return {
        field_name: truncated_value,
        f"{field_name}_is_truncated": True,
        f"{field_name}_total_chars": len(value),
        f"{field_name}_truncated_chars": int(len(value) - len(truncated_value)),
    }


def _field_is_already_truncated(field_name: str, value: JSONValue) -> bool:
    if not isinstance(value, bool):
        return False
    return field_name.endswith(_TRUNCATION_MARKERS[0][0]) or field_name.endswith(
        _TRUNCATION_MARKERS[1][0],
    )


def _serialized_chars(value: JSONValue) -> int:
    return len(serialize_json_compact_stable(value, ensure_ascii=False))


def _preview_limit_record(reason: str, total_count: int) -> dict[str, JSONValue]:
    return {
        "preview_omitted": True,
        "preview_omission_reason": reason,
        "preview_total_count": total_count,
    }


def _sanitize_mapping(value: Mapping[str, JSONValue], depth: int) -> dict[str, JSONValue]:
    if depth >= _PREVIEW_MAX_DEPTH:
        return _preview_limit_record("max_depth_exceeded", len(value))
    sanitized: dict[str, JSONValue] = {}
    emitted = 0
    for field_name, field_value in value.items():
        if emitted >= _PREVIEW_MAX_MAPPING_KEYS:
            sanitized["preview_omitted_fields"] = max(0, len(value) - emitted)
            sanitized["preview_omission_reason"] = "max_mapping_keys_exceeded"
            break
        if _field_is_already_truncated(field_name, field_value):
            sanitized[field_name] = field_value
            emitted += 1
            continue
        normalized_field_name = field_name.strip()
        if normalized_field_name.lower().endswith(_BINARY_FIELD_SUFFIX):
            if isinstance(field_value, str):
                sanitized[f"{normalized_field_name}_omitted"] = True
                sanitized[f"{normalized_field_name}_total_chars"] = len(field_value)
                sanitized[f"{normalized_field_name}_omission_reason"] = "inline_binary_removed"
                emitted += 1
                continue
            sanitized[normalized_field_name] = _sanitize_json_value(field_value, depth + 1)
            emitted += 1
            continue
        if isinstance(field_value, str) and len(field_value) > _PREVIEW_STRING_MAX_CHARS:
            sanitized.update(_build_truncated_string_record(normalized_field_name, field_value))
            emitted += 1
            continue
        sanitized[normalized_field_name] = _sanitize_json_value(field_value, depth + 1)
        emitted += 1
    return sanitized


def _sanitize_sequence(value: Sequence[JSONValue], depth: int) -> list[JSONValue]:
    if depth >= _PREVIEW_MAX_DEPTH:
        return [_preview_limit_record("max_depth_exceeded", len(value))]
    sanitized: list[JSONValue] = []
    for item in value[:_PREVIEW_MAX_SEQUENCE_ITEMS]:
        sanitized.append(_sanitize_json_value(item, depth + 1))
    omitted_count = len(value) - len(sanitized)
    if omitted_count > 0:
        sanitized.append(_preview_limit_record("max_sequence_items_exceeded", omitted_count))
    return sanitized


def _sanitize_json_value(value: JSONValue, depth: int) -> JSONValue:
    if isinstance(value, dict):
        return _sanitize_mapping(value, depth)
    if isinstance(value, list):
        return _sanitize_sequence(value, depth)
    return value


def _build_oversize_mapping_summary(value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    summary: dict[str, JSONValue] = {
        "preview_omitted": True,
        "preview_omission_reason": "serialized_preview_too_large",
        "preview_total_chars": _serialized_chars(dict(value)),
    }
    for field_name in _PREFERRED_SUMMARY_FIELDS:
        field_value = value.get(field_name)
        if field_value is not None:
            summary[field_name] = _sanitize_json_value(field_value, 1)
    media_markers = _extract_media_marker_summary(value, 0)
    for field_name, field_value in media_markers.items():
        if field_name not in summary:
            summary[field_name] = field_value
    return summary


def _media_marker_is_present(value: Mapping[str, JSONValue]) -> bool:
    omitted = value.get("image_base64_omitted") or value.get("video_base64_omitted")
    total_chars = value.get("image_base64_total_chars")
    if omitted is True:
        return True
    video_total_chars = value.get("video_base64_total_chars")
    return (isinstance(total_chars, int) and total_chars > 0) or (
        isinstance(video_total_chars, int) and video_total_chars > 0
    )


def _extract_inline_binary_media_fields(
    value: Mapping[str, JSONValue],
    *,
    binary_field_name: str,
) -> dict[str, JSONValue]:
    inline_base64 = value.get(binary_field_name)
    if not isinstance(inline_base64, str):
        return {}
    markers: dict[str, JSONValue] = {}
    for field_name in _MEDIA_MARKER_FIELDS:
        field_value = value.get(field_name)
        if field_value is not None:
            markers[field_name] = _sanitize_json_value(field_value, 1)
    marker_prefix = binary_field_name.removesuffix("_base64")
    markers[f"{marker_prefix}_base64_omitted"] = True
    markers[f"{marker_prefix}_base64_total_chars"] = len(inline_base64)
    markers[f"{marker_prefix}_base64_omission_reason"] = "inline_binary_removed"
    return markers


def _extract_direct_media_fields(value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    inline_binary_markers = _extract_inline_binary_media_fields(
        value,
        binary_field_name="image_base64",
    )
    if inline_binary_markers:
        return inline_binary_markers
    inline_binary_markers = _extract_inline_binary_media_fields(
        value,
        binary_field_name="video_base64",
    )
    if inline_binary_markers:
        return inline_binary_markers
    if not _media_marker_is_present(value):
        return {}
    markers: dict[str, JSONValue] = {}
    for field_name in _MEDIA_MARKER_FIELDS:
        field_value = value.get(field_name)
        if field_value is not None:
            markers[field_name] = _sanitize_json_value(field_value, 1)
    return markers


def _extract_preferred_mapping_fields(
    value: Mapping[str, JSONValue],
    depth: int,
) -> dict[str, JSONValue]:
    fields: dict[str, JSONValue] = {}
    for field_name in _PREFERRED_SUMMARY_FIELDS:
        field_value = value.get(field_name)
        if field_value is not None:
            fields[field_name] = _sanitize_json_value(field_value, depth + 1)
    return fields


def _extract_media_marker_summary(
    value: Mapping[str, JSONValue],
    depth: int,
) -> dict[str, JSONValue]:
    if depth >= _MEDIA_MARKER_MAX_DEPTH:
        return {}
    markers = _extract_direct_media_fields(value)
    for field_name in _MEDIA_CONTAINER_FIELDS:
        field_value = value.get(field_name)
        if not isinstance(field_value, dict):
            continue
        nested_markers = _extract_media_marker_summary(field_value, depth + 1)
        if nested_markers:
            nested_summary = _extract_preferred_mapping_fields(field_value, depth + 1)
            nested_summary.update(nested_markers)
            markers[field_name] = nested_summary
    return markers


def _fit_preview_size(original: JSONValue, preview: JSONValue) -> JSONValue:
    if _serialized_chars(preview) <= TIMELINE_TOOL_RESULT_PREVIEW_MAX_CHARS:
        return preview
    if isinstance(original, Mapping):
        return _build_oversize_mapping_summary(original)
    if isinstance(original, Sequence) and not isinstance(original, str):
        return _preview_limit_record("serialized_preview_too_large", len(original))
    if isinstance(original, str):
        return _build_truncated_string_record("value", original)
    return preview


def truncate_tool_result_payload_for_timeline(payload: JSONValue) -> JSONValue:
    return _fit_preview_size(payload, _sanitize_json_value(payload, 0))
