"""SoAI - File explorer route path guards [backend/features/api/routes/file_explorer/route_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SecurityError
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.file_explorer.path_resolution import canonicalize_virtual_path

__all__ = (
    "canonicalize_non_root_route_path",
    "canonicalize_non_root_route_paths",
    "require_non_root_route_path",
)


def canonicalize_non_root_route_path(
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    *,
    operation: str,
    message: str,
) -> str:
    canonical_path = canonicalize_virtual_path(root_scope, path)
    require_non_root_route_path(
        canonical_path,
        operation=operation,
        message=message,
    )
    return canonical_path


def canonicalize_non_root_route_paths(
    root_scope: FileSystemRootScopeProtocol,
    paths: list[str],
    *,
    operation: str,
    message: str,
) -> list[str]:
    return [
        canonicalize_non_root_route_path(
            root_scope,
            path,
            operation=operation,
            message=message,
        )
        for path in paths
    ]


def require_non_root_route_path(
    path: str,
    *,
    operation: str,
    message: str,
) -> None:
    if path == "/":
        raise SecurityError(message, operation=operation)
