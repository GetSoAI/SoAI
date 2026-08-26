"""SoAI - Backup manifest validation [backend/core/backup/manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import posixpath
import re
from typing import TYPE_CHECKING

from core.backup.paths import (
    ALLOWED_RESTORE_DIRECTORY_DESTINATION_KEYS,
    ALLOWED_RESTORE_FILE_DESTINATION_KEYS,
)
from core.errors.exceptions import SecurityError, ValidationError
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ensure_allowed_restore_target",
    "normalize_manifest_files_map",
    "normalize_manifest_rel_path",
    "validate_backup_id",
    "validate_sha256_hash",
)

BACKUP_ID_REGEX = r"^soai_backup_\d{8}_\d{6}(?:_\d+)?$"
SHA256_HEX_REGEX = r"^[a-f0-9]{64}$"


def validate_backup_id(backup_id: str) -> str:
    normalized = (backup_id or "").strip()
    if not normalized:
        raise ValidationError("backup_id is required.")
    if "\x00" in normalized:
        raise SecurityError("backup_id contains NUL byte.")
    if re.fullmatch(BACKUP_ID_REGEX, normalized) is None:
        raise ValidationError("Invalid backup_id format.")
    path_separators = {"/", "\\", os.sep}
    if os.altsep:
        path_separators.add(os.altsep)
    if any(separator in normalized for separator in path_separators):
        raise SecurityError("backup_id contains path separators.")
    return normalized


def validate_sha256_hash(hash_value: JSONValue, context: str) -> str:
    if not isinstance(hash_value, str):
        raise ValidationError(f"SHA256 hash must be a string for {context}.")
    normalized = hash_value.strip().lower()
    if not normalized:
        raise ValidationError(f"SHA256 hash is required for {context}.")
    if re.fullmatch(SHA256_HEX_REGEX, normalized) is None:
        raise ValidationError(
            f"Invalid SHA256 hash format for {context}: expected 64 lowercase hex characters.",
        )
    return normalized


def normalize_manifest_rel_path(rel_path: str) -> str:
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValidationError("Manifest path must be a non-empty string.")
    if "\x00" in rel_path:
        raise SecurityError("Manifest path contains NUL byte.")
    stripped = rel_path.strip()
    if stripped.startswith("/"):
        raise SecurityError(f"Absolute restore path is not allowed: {rel_path}")
    if "\\" in stripped:
        raise SecurityError(f"Backslashes are not allowed in restore path: {rel_path}")
    normalized = posixpath.normpath(stripped)
    if normalized in {".", ""}:
        raise ValidationError(f"Invalid restore path: {rel_path}")
    if normalized == ".." or normalized.startswith("../"):
        raise SecurityError(f"Restore path escapes base directory: {rel_path}")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        raise ValidationError(f"Invalid restore path: {rel_path}")
    if any(part in {".", ".."} for part in parts):
        raise SecurityError(f"Invalid restore path traversal: {rel_path}")
    return normalized


def normalize_manifest_files_map(
    raw_manifest_files: JSONDict,
) -> JSONDict:
    if not isinstance(raw_manifest_files, dict):
        raise ValidationError("Manifest files must be a dictionary.")
    normalized_files: JSONDict = {}
    for raw_rel_path, file_info in raw_manifest_files.items():
        normalized_rel_path = normalize_manifest_rel_path(str(raw_rel_path))
        normalized_files[normalized_rel_path] = file_info
    return normalized_files


def ensure_allowed_restore_target(rel_path: str, file_info: JSONDict) -> None:
    if not isinstance(file_info, dict):
        raise ValidationError(f"Manifest entry must be an object for {rel_path}.")
    entry_type = file_info.get("type")
    if entry_type not in {"file", "directory"}:
        raise ValidationError(f"Manifest entry missing valid type for {rel_path}.")
    if any(
        rel_path == posixpath.join(*path_parts)
        for path_parts, _dest in ALLOWED_RESTORE_FILE_DESTINATION_KEYS
    ):
        if entry_type != "file":
            raise ValidationError(f"Manifest entry type mismatch for {rel_path}.")
        return
    if any(
        rel_path == posixpath.join(*path_parts)
        for path_parts, _dest in ALLOWED_RESTORE_DIRECTORY_DESTINATION_KEYS
    ):
        if entry_type != "directory":
            raise ValidationError(f"Manifest entry type mismatch for {rel_path}.")
        return
    if rel_path.startswith("plugins/"):
        if entry_type != "file":
            raise ValidationError(f"Manifest entry type mismatch for {rel_path}.")
        file_name = rel_path[len("plugins/") :]
        if not file_name or "/" in file_name:
            raise SecurityError(f"Invalid plugin restore path: {rel_path}")
        if not file_name.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
            raise ValidationError(
                f"Only plugin config files may be restored under plugins/: {rel_path}",
            )
        return
    raise SecurityError(f"Restore target is not allowed: {rel_path}")
