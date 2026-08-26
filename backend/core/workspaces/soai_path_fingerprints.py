"""SoAI - SoAI path target fingerprinting [backend/core/workspaces/soai_path_fingerprints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence

from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.workspace_descriptor import open_workspace_file_descriptor
from core.files.workspace_listing import (
    WorkspaceDirectoryEntry,
    list_workspace_directory,
)
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict

__all__ = (
    "build_soai_path_folder_listing_fingerprint_value",
    "build_soai_path_target_fingerprint",
    "require_soai_path_fingerprint_value",
)

_FINGERPRINT_PREFIX = "sha256:"
_SHA256_HEX_CHARS = frozenset("0123456789abcdef")


def require_soai_path_fingerprint_value(value: str, *, field: str) -> str:
    normalized = value.strip()
    if normalized != value or not normalized.startswith(_FINGERPRINT_PREFIX):
        raise ValidationError(f"SoAI path {field} must be a canonical sha256 fingerprint.")
    digest = normalized.removeprefix(_FINGERPRINT_PREFIX)
    if len(digest) != 64 or any(character not in _SHA256_HEX_CHARS for character in digest):
        raise ValidationError(f"SoAI path {field} must be a canonical sha256 fingerprint.")
    return normalized


def _folder_listing_payload(entries: Sequence[WorkspaceDirectoryEntry]) -> str:
    payload: list[JSONDict] = []
    for entry in sorted(entries, key=lambda item: (item.name, item.entry_type)):
        payload.append(
            {
                "name": entry.name,
                "type": entry.entry_type,
                "size_bytes": entry.size_bytes,
                "modified_at_ms": entry.modified_at_ms,
            },
        )
    return serialize_json_compact_stable(payload)


def build_soai_path_folder_listing_fingerprint_value(
    entries: Sequence[WorkspaceDirectoryEntry],
) -> str:
    payload = _folder_listing_payload(entries)
    digest = hashlib.sha256(payload.encode("utf-8", errors="surrogateescape")).hexdigest()
    return f"{_FINGERPRINT_PREFIX}{digest}"


def _file_fingerprint(
    *,
    effective_workspace_root: str,
    conversation_virtual_path: str,
) -> JSONDict:
    opened = open_workspace_file_descriptor(
        effective_workspace_root,
        conversation_virtual_path,
        error_cls=ValidationError,
    )
    try:
        content_hash = hash_descriptor_content(opened.descriptor)
    finally:
        os.close(opened.descriptor)
    return {
        "type": "file_sha256",
        "value": f"{_FINGERPRINT_PREFIX}{content_hash.sha256_hex}",
    }


def _folder_fingerprint(
    *,
    effective_workspace_root: str,
    conversation_virtual_path: str,
) -> JSONDict:
    entries = list_workspace_directory(
        effective_workspace_root,
        conversation_virtual_path,
        error_cls=ValidationError,
    )
    return {
        "type": "folder_listing_sha256",
        "value": build_soai_path_folder_listing_fingerprint_value(entries),
    }


def build_soai_path_target_fingerprint(
    *,
    effective_workspace_root: str,
    conversation_virtual_path: str,
    entry_type: str,
) -> JSONDict:
    if entry_type == "file":
        return _file_fingerprint(
            effective_workspace_root=effective_workspace_root,
            conversation_virtual_path=conversation_virtual_path,
        )
    if entry_type == "folder":
        return _folder_fingerprint(
            effective_workspace_root=effective_workspace_root,
            conversation_virtual_path=conversation_virtual_path,
        )
    raise ValidationError("SoAI path entry_type is invalid.")
