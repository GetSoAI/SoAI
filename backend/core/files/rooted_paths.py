"""SoAI - Root-scoped user path resolution helpers [backend/core/files/rooted_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.path_policy import ensure_path_within_base

__all__ = (
    "resolve_rooted_candidate_path",
    "resolve_rooted_existing_dir",
    "resolve_rooted_existing_file",
    "resolve_rooted_path",
)


def resolve_rooted_candidate_path(path_value: str, *, base_path: str) -> str:
    stripped = path_value.strip()
    if os.path.isabs(stripped):
        candidate = stripped
    else:
        candidate = os.path.join(base_path, stripped)
    return os.path.realpath(os.path.abspath(candidate))


def resolve_rooted_path(
    path_value: str,
    *,
    base_path: str,
    description: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    stripped = path_value.strip()
    if not stripped:
        raise error_cls(f"{description} cannot be empty.")
    candidate = resolve_rooted_candidate_path(stripped, base_path=base_path)
    return ensure_path_within_base(
        base_path,
        candidate,
        description=description,
        error_cls=error_cls,
    )


def resolve_rooted_existing_dir(
    path_value: str,
    *,
    base_path: str,
    description: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    resolved = resolve_rooted_path(
        path_value,
        base_path=base_path,
        description=description,
        error_cls=error_cls,
    )
    if not os.path.isdir(resolved):
        raise error_cls(f"{description} is not a directory: {path_value}")
    return resolved


def resolve_rooted_existing_file(
    path_value: str,
    *,
    base_path: str,
    description: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    resolved = resolve_rooted_path(
        path_value,
        base_path=base_path,
        description=description,
        error_cls=error_cls,
    )
    if os.path.isdir(resolved):
        raise error_cls(
            f"{description} is a directory: {path_value}. Use list_dir for directories."
        )
    if not os.path.exists(resolved):
        raise error_cls(f"{description} does not exist: {path_value}")
    if not os.path.isfile(resolved):
        raise error_cls(f"{description} is not a file: {path_value}")
    return resolved
