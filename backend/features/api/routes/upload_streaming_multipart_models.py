"""SoAI - Streaming multipart types and validation helpers [backend/features/api/routes/upload_streaming_multipart_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError

__all__ = (
    "DEFAULT_MULTIPART_METADATA_LIMIT_BYTES",
    "StreamingMultipartResult",
    "StreamingMultipartSpec",
    "StreamingStagedPart",
    "decode_multipart_header_value",
)

DEFAULT_MULTIPART_METADATA_LIMIT_BYTES = 8 * MIB_BYTES


def decode_multipart_header_value(value: bytes | None, *, field: str) -> str:
    if value is None:
        raise ValidationError(f"Missing {field}.")
    try:
        decoded = value.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ValidationError(f"Invalid {field} encoding.") from exception
    normalized = decoded.strip()
    if not normalized:
        raise ValidationError(f"Missing {field}.")
    return normalized


@dataclass(frozen=True, slots=True)
class StreamingStagedPart:
    field_name: str
    original_filename: str
    temp_path: str
    size_bytes: int
    content_sha256: str
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class StreamingMultipartResult:
    fields: dict[str, tuple[str, ...]]
    files: list[StreamingStagedPart]


@dataclass(frozen=True, slots=True)
class StreamingMultipartSpec:
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]
    required_file_fields: frozenset[str]
    allowed_file_fields: frozenset[str]
    allow_multiple_files: bool
    require_fields_before_files: bool
    temp_dir: str
    max_file_bytes: int | None
    max_total_file_bytes: int | None
    max_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES
    max_total_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES
