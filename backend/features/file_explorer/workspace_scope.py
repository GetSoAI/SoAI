"""SoAI - File system root scope for path validation and traversal prevention [backend/features/file_explorer/workspace_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import SecurityError, ValidationError
from core.files.path_policy import (
    ensure_path_within_base,
    ensure_path_within_base_lexical,
)
from core.files.workspace_path import resolve_existing_workspace_directory
from features.file_explorer.path_validation import sanitize_virtual_path

__all__ = ("FileSystemRootScope",)


class FileSystemRootScope:
    __slots__ = ("_allow_symlinks", "root_path")

    def __init__(self, *, root_path: str, allow_symlinks: bool) -> None:
        self.root_path = resolve_existing_workspace_directory(root_path)
        self._allow_symlinks = allow_symlinks

    def resolve(self, virtual_path: str) -> str:
        sanitized = sanitize_virtual_path(virtual_path)
        candidate = os.path.join(self.root_path, sanitized)
        lexical_candidate = ensure_path_within_base_lexical(
            self.root_path,
            candidate,
            description="File explorer path",
            error_cls=SecurityError,
        )
        if not self._allow_symlinks:
            _reject_symlink_in_chain(self.root_path, lexical_candidate)
        return ensure_path_within_base(
            self.root_path,
            lexical_candidate,
            description="File explorer path",
            error_cls=SecurityError,
        )

    def validate(self, real_path: str) -> str:
        return ensure_path_within_base(
            self.root_path,
            real_path,
            description="File explorer path",
            error_cls=SecurityError,
        )

    def to_virtual_path(self, real_path: str) -> str:
        lexical_path = ensure_path_within_base_lexical(
            self.root_path,
            real_path,
            description="File explorer path",
            error_cls=SecurityError,
        )
        self.validate(lexical_path)
        relative = os.path.relpath(lexical_path, self.root_path)
        if relative == ".":
            return "/"
        return f"/{relative.replace(os.sep, '/')}"

    def canonicalize_virtual_path(self, virtual_path: str) -> str:
        sanitized = sanitize_virtual_path(virtual_path)
        if not sanitized:
            return "/"
        return f"/{sanitized.replace(os.sep, '/')}"

    def ensure_root_exists(self) -> None:
        if not os.path.isdir(self.root_path):
            raise ValidationError(
                "workspace_path must be an existing directory.",
                operation="file_explorer.ensure_root_exists",
            )


def _reject_symlink_in_chain(root_path: str, resolved_path: str) -> None:
    relative = os.path.relpath(resolved_path, root_path)
    if relative == ".":
        return
    parts = relative.split(os.sep)
    current = root_path
    for part in parts:
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise SecurityError(
                f"Symbolic links are not allowed: '{part}'.",
                operation="file_explorer.reject_symlink",
            )
