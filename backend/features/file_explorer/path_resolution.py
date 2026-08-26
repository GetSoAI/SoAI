"""SoAI - File explorer path resolution [backend/features/file_explorer/path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, ValidationError
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.upload_relative_paths import normalize_batch_upload_relative_path

if TYPE_CHECKING:
    from core.files.protocols_explorer import (
        FileExplorerCoreProtocol,
        FileSystemRootScopeProtocol,
    )
    from features.file_explorer.internal_protocols import SecureFileOpsProtocol

__all__ = (
    "canonicalize_virtual_path",
    "resolve_download_archive_real_path",
    "resolve_batch_upload_virtual_destination",
    "resolve_download_real_path",
    "resolve_existing_real_path",
    "resolve_single_upload_virtual_destination",
    "resolve_upload_destination",
)


def canonicalize_virtual_path(root_scope: FileSystemRootScopeProtocol, virtual_path: str) -> str:
    try:
        canonical_path = root_scope.canonicalize_virtual_path(virtual_path)
    except ValueError as exception:
        raise ValidationError(
            "Invalid virtual path.",
            operation="file_explorer.canonicalize_virtual_path",
        ) from exception
    if not canonical_path.startswith("/"):
        raise ValidationError("Canonical virtual path must be absolute.")
    return canonical_path


def resolve_download_real_path(root_scope: FileSystemRootScopeProtocol, virtual_path: str) -> str:
    canonical_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(canonical_path)
    if not os.path.isfile(real_path) and not os.path.isdir(real_path):
        raise NotFoundError(
            f"File not found: '{canonical_path}'.",
            operation="file_explorer.download",
        )
    return real_path


def resolve_download_archive_real_path(
    root_scope: FileSystemRootScopeProtocol,
    virtual_path: str,
) -> str:
    canonical_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = ensure_path_within_base_lexical(
        root_scope.root_path,
        os.path.join(root_scope.root_path, canonical_path.lstrip("/")),
        description="File explorer download archive path",
        error_cls=ValidationError,
    )
    if not os.path.lexists(real_path):
        raise NotFoundError(
            f"File not found: '{canonical_path}'.",
            operation="file_explorer.download_archive",
        )
    return real_path


def resolve_existing_real_path(root_scope: FileSystemRootScopeProtocol, virtual_path: str) -> str:
    canonical_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(canonical_path)
    if not os.path.exists(real_path):
        raise NotFoundError(
            f"Path not found: '{canonical_path}'.",
            operation="file_explorer.resolve_real_path",
        )
    return real_path


def resolve_single_upload_virtual_destination(
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    *,
    base_path: str,
    safe_filename: str,
) -> str:
    return file_explorer_core.canonicalize_virtual_path(
        root_scope,
        base_path.rstrip("/") + f"/{safe_filename}",
    )


def resolve_batch_upload_virtual_destination(
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    *,
    base_path: str,
    relative_path: str,
) -> str:
    safe_relative_path = normalize_batch_upload_relative_path(relative_path)
    return file_explorer_core.canonicalize_virtual_path(
        root_scope,
        base_path.rstrip("/") + f"/{safe_relative_path}",
    )


def resolve_upload_destination(
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    virtual_path: str,
    *,
    create_missing_parents: bool = False,
) -> str:
    canonical_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(canonical_path)
    parent_dir = os.path.dirname(real_path)
    if create_missing_parents and parent_dir and not os.path.isdir(parent_dir):
        try:
            secure_ops.create_directory(parent_dir)
        except (FileExistsError, NotADirectoryError) as exception:
            raise ValidationError(
                "Upload destination parent path is not a directory.",
            ) from exception
    if not os.path.isdir(parent_dir):
        raise NotFoundError(
            "Upload destination parent directory does not exist.",
            operation="file_explorer.upload",
        )
    if os.path.exists(real_path):
        raise ValidationError(
            "A file or directory with this name already exists.",
        )
    return real_path
