"""SoAI - Shared upload relative path validation [backend/core/files/upload_relative_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("normalize_batch_upload_relative_path",)

_FORBIDDEN_PATH_CHARACTERS: tuple[str, ...] = (":", "*", "?", '"', "<", ">", "|")


def normalize_batch_upload_relative_path(relative_path: str) -> str:
    if not relative_path:
        raise ValidationError("Empty relative path")
    if "\x00" in relative_path:
        raise ValidationError("Invalid relative path")
    if any(forbidden in relative_path for forbidden in _FORBIDDEN_PATH_CHARACTERS):
        raise ValidationError("Invalid relative path")
    if relative_path.startswith(("/", "\\")) or relative_path.endswith(("/", "\\")):
        raise ValidationError("Invalid relative path")
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    if "" in parts:
        raise ValidationError("Invalid relative path")
    for part in parts:
        if part != part.strip():
            raise ValidationError("Invalid relative path")
    if "." in parts or normalized in {".", ".."}:
        raise ValidationError("Invalid relative path")
    if ".." in parts:
        raise ValidationError("Path traversal not allowed")
    return normalized
