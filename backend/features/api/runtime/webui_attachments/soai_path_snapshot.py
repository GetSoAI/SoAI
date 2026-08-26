"""SoAI - Verified SoAI path provider snapshots [backend/features/api/runtime/webui_attachments/soai_path_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.workspace_descriptor import open_workspace_file_descriptor
from core.files.workspace_listing import (
    WorkspaceDirectoryEntry,
    list_workspace_directory,
)
from core.workspaces.soai_path_fingerprints import (
    build_soai_path_folder_listing_fingerprint_value,
)
from core.workspaces.soai_path_part_fields import (
    source_reference_value,
    target_fingerprint_value,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "load_verified_soai_path_folder_entries",
    "open_verified_soai_path_file_descriptor",
)


def open_verified_soai_path_file_descriptor(
    *,
    effective_root: str,
    canonical: JSONDict,
) -> int | None:
    opened = open_workspace_file_descriptor(
        effective_root,
        source_reference_value(canonical),
        error_cls=ValidationError,
    )
    completed = False
    try:
        content_hash = hash_descriptor_content(opened.descriptor)
        size_bytes = canonical.get("size_bytes")
        if (
            not isinstance(size_bytes, int)
            or content_hash.size_bytes != size_bytes
            or f"sha256:{content_hash.sha256_hex}" != target_fingerprint_value(canonical)
        ):
            return None
        completed = True
        return opened.descriptor
    finally:
        if not completed:
            os.close(opened.descriptor)


def load_verified_soai_path_folder_entries(
    *,
    effective_root: str,
    canonical: JSONDict,
) -> list[WorkspaceDirectoryEntry] | None:
    entries = list_workspace_directory(
        effective_root,
        source_reference_value(canonical),
        error_cls=ValidationError,
    )
    if build_soai_path_folder_listing_fingerprint_value(entries) != target_fingerprint_value(
        canonical,
    ):
        return None
    return entries
