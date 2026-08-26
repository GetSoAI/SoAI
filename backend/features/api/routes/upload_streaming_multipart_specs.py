"""SoAI - Canonical streaming multipart spec constructors [backend/features/api/routes/upload_streaming_multipart_specs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.upload_validation import normalize_positive_size_strict
from features.api.routes.upload_streaming_multipart_models import (
    DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    StreamingMultipartSpec,
)

__all__ = (
    "build_streaming_multipart_spec",
    "relative_paths_sizes_files_upload_spec",
    "size_bytes_single_file_upload_spec",
)


def build_streaming_multipart_spec(
    *,
    required_fields: frozenset[str],
    allowed_fields: frozenset[str],
    required_file_fields: frozenset[str],
    allowed_file_fields: frozenset[str],
    allow_multiple_files: bool,
    require_fields_before_files: bool,
    temp_dir: str,
    max_file_bytes: int | None,
    max_total_file_bytes: int | None,
    max_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    max_total_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
) -> StreamingMultipartSpec:
    normalized_file = None
    if max_file_bytes is not None:
        normalized_file = normalize_positive_size_strict(
            max_file_bytes,
            field_name="max_file_bytes",
        )
    normalized_total = None
    if max_total_file_bytes is not None:
        normalized_total = normalize_positive_size_strict(
            max_total_file_bytes,
            field_name="max_total_file_bytes",
        )
    return StreamingMultipartSpec(
        required_fields=required_fields,
        allowed_fields=allowed_fields,
        required_file_fields=required_file_fields,
        allowed_file_fields=allowed_file_fields,
        allow_multiple_files=allow_multiple_files,
        require_fields_before_files=require_fields_before_files,
        temp_dir=temp_dir,
        max_file_bytes=normalized_file,
        max_total_file_bytes=normalized_total,
        max_field_bytes=normalize_positive_size_strict(
            max_field_bytes,
            field_name="max_field_bytes",
        ),
        max_total_field_bytes=normalize_positive_size_strict(
            max_total_field_bytes,
            field_name="max_total_field_bytes",
        ),
    )


def size_bytes_single_file_upload_spec(
    temp_dir: str,
    *,
    max_upload_bytes: int | None,
    max_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    max_total_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
) -> StreamingMultipartSpec:
    normalized_max = None
    if max_upload_bytes is not None:
        normalized_max = normalize_positive_size_strict(
            max_upload_bytes,
            field_name="max_upload_bytes",
        )
    return build_streaming_multipart_spec(
        required_fields=frozenset({"size_bytes"}),
        allowed_fields=frozenset({"size_bytes", "content_type"}),
        required_file_fields=frozenset({"file"}),
        allowed_file_fields=frozenset({"file"}),
        allow_multiple_files=False,
        require_fields_before_files=True,
        temp_dir=temp_dir,
        max_file_bytes=normalized_max,
        max_total_file_bytes=normalized_max,
        max_field_bytes=max_field_bytes,
        max_total_field_bytes=max_total_field_bytes,
    )


def relative_paths_sizes_files_upload_spec(
    temp_dir: str,
    *,
    max_upload_bytes: int | None,
    max_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    max_total_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
) -> StreamingMultipartSpec:
    normalized_max = None
    if max_upload_bytes is not None:
        normalized_max = normalize_positive_size_strict(
            max_upload_bytes,
            field_name="max_upload_bytes",
        )
    return build_streaming_multipart_spec(
        required_fields=frozenset({"relative_paths", "relative_sizes"}),
        allowed_fields=frozenset({"relative_paths", "relative_sizes"}),
        required_file_fields=frozenset({"files"}),
        allowed_file_fields=frozenset({"files"}),
        allow_multiple_files=True,
        require_fields_before_files=True,
        temp_dir=temp_dir,
        max_file_bytes=normalized_max,
        max_total_file_bytes=None,
        max_field_bytes=max_field_bytes,
        max_total_field_bytes=max_total_field_bytes,
    )
