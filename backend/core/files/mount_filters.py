"""SoAI - Mount point filtering helpers [backend/core/files/mount_filters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("is_internal_mount_entry", "is_internal_mount_point")

_INTERNAL_FILESYSTEM_TYPES: frozenset[str] = frozenset(("nsfs",))


def _matches_path_or_child(path: str, base_path: str) -> bool:
    return path == base_path or path.startswith(base_path + os.sep)


def is_internal_mount_point(mount_point: str) -> bool:
    normalized = str(mount_point or "").strip()
    if not normalized:
        return True
    docker_netns_run = os.path.join(os.sep, "run", "docker", "netns")
    docker_netns_var_run = os.path.join(os.sep, "var", "run", "docker", "netns")
    docker_linux_prefix = os.path.join(os.sep, "var", "lib", "docker") + os.sep
    program_data = os.environ.get("ProgramData", "") or os.environ.get("PROGRAMDATA", "") or ""
    docker_windows_prefix = (
        (os.path.join(program_data, "docker") + os.sep).lower() if program_data else ""
    )
    lower = normalized.lower()
    return (
        _matches_path_or_child(normalized, docker_netns_run)
        or _matches_path_or_child(normalized, docker_netns_var_run)
        or normalized.startswith(docker_linux_prefix)
        or (docker_windows_prefix and lower.startswith(docker_windows_prefix))
        or (":\\users\\" in lower and "\\appdata\\local\\docker\\" in lower)
        or (lower.startswith("\\\\wsl") and "docker" in lower)
    )


def is_internal_mount_entry(mount_point: str, filesystem_type: str | None) -> bool:
    normalized_filesystem_type = str(filesystem_type or "").strip().lower()
    return (
        is_internal_mount_point(mount_point)
        or normalized_filesystem_type in _INTERNAL_FILESYSTEM_TYPES
    )
