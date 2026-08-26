"""SoAI - File explorer path validation rules [backend/features/file_explorer/path_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import SecurityError, ValidationError

__all__ = (
    "normalize_upload_filename",
    "sanitize_virtual_path",
)

_FORBIDDEN_PATH_CHARACTERS: tuple[str, ...] = (":", "*", "?", '"', "<", ">", "|")


def sanitize_virtual_path(virtual_path: str) -> str:
    if not isinstance(virtual_path, str):
        raise ValidationError(
            "Virtual path must be a string.",
            operation="file_explorer.sanitize_path",
        )
    if virtual_path != virtual_path.strip():
        raise ValidationError(
            "Invalid virtual path.",
            operation="file_explorer.sanitize_path",
        )
    if "\x00" in virtual_path:
        raise ValidationError(
            "Invalid virtual path.",
            operation="file_explorer.sanitize_path",
        )
    if any(forbidden in virtual_path for forbidden in _FORBIDDEN_PATH_CHARACTERS):
        raise ValidationError(
            "Invalid virtual path.",
            operation="file_explorer.sanitize_path",
        )
    if "\\" in virtual_path:
        raise ValidationError(
            "Invalid virtual path.",
            operation="file_explorer.sanitize_path",
        )
    if not virtual_path or virtual_path == "/":
        return ""
    normalized = os.path.normpath(virtual_path.lstrip("/"))
    if normalized == ".":
        return ""
    parts = normalized.split(os.sep)
    for part in parts:
        if part != part.strip():
            raise ValidationError(
                "Invalid virtual path.",
                operation="file_explorer.sanitize_path",
            )
    if any(part == ".." for part in parts):
        raise SecurityError(
            "Path traversal is not allowed.",
            operation="file_explorer.sanitize_path",
        )
    return normalized


def normalize_upload_filename(filename: str | None) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValidationError("Uploaded file must have a filename.")
    if filename != filename.strip():
        raise ValidationError("Invalid filename.")
    if "\x00" in filename:
        raise ValidationError("Invalid filename.")
    safe_filename = os.path.basename(filename.replace("\\", "/"))
    if not safe_filename or safe_filename in {".", ".."}:
        raise ValidationError("Invalid filename.")
    if any(forbidden in safe_filename for forbidden in _FORBIDDEN_PATH_CHARACTERS):
        raise ValidationError("Invalid filename.")
    if safe_filename != safe_filename.strip():
        raise ValidationError("Invalid filename.")
    return safe_filename
