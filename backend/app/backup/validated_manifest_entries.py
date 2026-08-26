"""SoAI - Canonical backup manifest entry validation [backend/app/backup/validated_manifest_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.backup.manifest import (
    ensure_allowed_restore_target,
    normalize_manifest_rel_path,
    validate_sha256_hash,
)
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ValidatedManifestEntry",
    "build_validated_manifest_entries",
    "require_manifest_files_payload",
)


@dataclass(frozen=True, slots=True)
class ValidatedManifestEntry:
    rel_path: str
    file_info: JSONDict
    entry_type: str
    size_bytes: int
    sha256_hash: str


def require_manifest_files_payload(payload: JSONValue) -> JSONDict:
    if not isinstance(payload, dict) or not payload:
        raise ValidationError("Backup manifest contains no files.")
    return payload


def build_validated_manifest_entries(files: JSONValue) -> list[ValidatedManifestEntry]:
    files_payload = require_manifest_files_payload(files)
    validated_entries: list[ValidatedManifestEntry] = []
    for raw_rel_path, file_info in files_payload.items():
        rel_path = normalize_manifest_rel_path(str(raw_rel_path))
        if not isinstance(file_info, dict):
            raise ValidationError(f"Manifest entry for {rel_path} must be an object.")
        ensure_allowed_restore_target(rel_path, file_info)
        entry_type = file_info.get("type")
        if entry_type not in {"file", "directory"}:
            raise ValidationError(f"Invalid manifest entry type for {rel_path}.")
        size_value = file_info.get("size")
        if not is_strict_int(size_value) or size_value < 0:
            raise ValidationError(f"Manifest entry missing valid size for {rel_path}.")
        validated_entries.append(
            ValidatedManifestEntry(
                rel_path=rel_path,
                file_info=file_info,
                entry_type=str(entry_type),
                size_bytes=size_value,
                sha256_hash=validate_sha256_hash(file_info.get("sha256"), rel_path),
            ),
        )
    validated_entries.sort(key=lambda item: item.rel_path)
    return validated_entries
