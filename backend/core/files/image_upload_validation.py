"""SoAI - Shared staged image upload validation [backend/core/files/image_upload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.files.content_types import normalize_content_type
from core.files.image_signature import (
    ALLOWED_IMAGE_CONTENT_TYPES,
    ALLOWED_IMAGE_EXTENSIONS,
    validate_image_signature,
)
from core.files.upload_size_validation import ensure_staged_size_matches_declared
from core.files.upload_validation import normalize_non_negative_size_strict
from core.filesystem.open_files import open_binary

__all__ = (
    "ValidatedStagedImage",
    "validate_staged_image_upload",
)


def _resolve_allowed_extensions_for_mime(mime_type: str) -> tuple[str, ...] | None:
    match mime_type:
        case "image/png":
            return (".png",)
        case "image/jpeg":
            return (".jpg", ".jpeg")
        case "image/gif":
            return (".gif",)
        case "image/webp":
            return (".webp",)
        case _:
            return None


@dataclass(frozen=True, slots=True)
class ValidatedStagedImage:
    extension: str
    detected_content_type: str
    size_bytes: int


def _extract_image_extension(filename: str) -> str | None:
    extension = os.path.splitext(filename)[1].lower()
    if not extension:
        return None
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Invalid file extension '{extension}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )
    return extension


def _validate_declared_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    normalized_content_type = normalize_content_type(content_type)
    if not normalized_content_type:
        return None
    if normalized_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(
            f"Invalid content type '{content_type}'. Allowed: {', '.join(ALLOWED_IMAGE_CONTENT_TYPES)}",
        )
    return normalized_content_type


def _read_file_prefix(file_path: str, *, byte_count: int) -> bytes:
    with open_binary(file_path, mode="rb") as file_handle:
        return file_handle.read(byte_count)


def validate_staged_image_upload(
    *,
    staged_file_path: str,
    original_filename: str,
    content_type: str | None,
    declared_size_bytes: int | None,
    max_size_bytes: int,
) -> ValidatedStagedImage:
    normalized_max_size_bytes = normalize_non_negative_size_strict(
        max_size_bytes,
        field_name="max_size_bytes",
    )
    if normalized_max_size_bytes is None or normalized_max_size_bytes <= 0:
        raise ValidationError("max_size_bytes must be > 0.")
    extension_from_name = _extract_image_extension(original_filename)
    normalized_content_type = _validate_declared_content_type(content_type)
    normalized_declared_size = normalize_non_negative_size_strict(
        declared_size_bytes,
        field_name="declared_size_bytes",
    )
    if (
        normalized_declared_size is not None
        and normalized_declared_size > normalized_max_size_bytes
    ):
        raise ValidationError(
            f"File size of {normalized_declared_size / 1024 / 1024:.2f}MB exceeds the limit of {normalized_max_size_bytes / 1024 / 1024:.2f}MB.",
        )
    try:
        size_bytes = int(os.path.getsize(staged_file_path))
    except OSError as exception:
        raise ValidationError(f"Failed to read staged image size: {exception}") from exception
    ensure_staged_size_matches_declared(
        declared_size=normalized_declared_size,
        staged_size=size_bytes,
    )
    if size_bytes > normalized_max_size_bytes:
        raise ValidationError(
            f"File size of {size_bytes / 1024 / 1024:.2f}MB exceeds the limit of {normalized_max_size_bytes / 1024 / 1024:.2f}MB.",
        )
    try:
        prefix = _read_file_prefix(staged_file_path, byte_count=32)
    except OSError as exception:
        raise ValidationError(f"Failed to read staged image content: {exception}") from exception
    is_valid_signature, detected_content_type = validate_image_signature(prefix)
    if not is_valid_signature or detected_content_type is None:
        raise ValidationError(
            "File does not appear to be a valid image (magic byte signature mismatch).",
        )
    allowed_extensions = _resolve_allowed_extensions_for_mime(detected_content_type)
    if not allowed_extensions:
        raise ValidationError(f"Unsupported detected image MIME type '{detected_content_type}'.")
    resolved_extension = allowed_extensions[0]
    if extension_from_name is not None and extension_from_name not in allowed_extensions:
        raise ValidationError(
            f"Image extension mismatch: filename extension '{extension_from_name}' is incompatible with detected type '{detected_content_type}'.",
        )
    if normalized_content_type is not None and detected_content_type != normalized_content_type:
        raise ValidationError(
            f"Image content type mismatch: declared '{normalized_content_type}', detected '{detected_content_type}'.",
        )
    return ValidatedStagedImage(
        extension=resolved_extension,
        detected_content_type=detected_content_type,
        size_bytes=size_bytes,
    )
