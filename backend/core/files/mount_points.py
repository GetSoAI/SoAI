"""SoAI - Mount point resolution helpers [backend/core/files/mount_points.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ProcessError, ValidationError
from core.filesystem.open_files import open_text
from core.validation.requirements import require_nonempty_str

__all__ = (
    "decode_escaped_path",
    "resolve_mount_point_for_path",
    "resolve_mount_points",
)

_PROC_MOUNTINFO_PATH = "/proc/self/mountinfo"


def resolve_mount_points(mountinfo_path: str = _PROC_MOUNTINFO_PATH) -> tuple[str, ...]:
    path = require_nonempty_str(mountinfo_path, field="mountinfo_path")
    try:
        with open_text(path, mode="r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError as exception:
        raise ProcessError(
            "Failed to read mount information.",
            operation="core.files.mount_points.read",
            details={"mountinfo_path": path},
        ) from exception
    mount_points: list[str] = []
    for raw_line in lines:
        fields = raw_line.split()
        if len(fields) < 5:
            continue
        mount_point = decode_escaped_path(fields[4])
        if mount_point:
            mount_points.append(mount_point)
    return tuple(mount_points)


def resolve_mount_point_for_path(
    candidate_path: str,
    *,
    mountinfo_path: str = _PROC_MOUNTINFO_PATH,
) -> str:
    normalized_path = require_nonempty_str(candidate_path, field="candidate_path")
    absolute_path = os.path.realpath(os.path.abspath(normalized_path))
    if not os.path.isabs(absolute_path):
        raise ValidationError("candidate_path must be an absolute path.")
    best_match: str | None = None
    for mount_point in resolve_mount_points(mountinfo_path):
        if not _path_contains(mount_point, absolute_path):
            continue
        if best_match is None or len(mount_point) > len(best_match):
            best_match = mount_point
    if best_match is None:
        raise ValidationError(f"No mount point found for path: {absolute_path}")
    return best_match


def _path_contains(base_path: str, candidate_path: str) -> bool:
    try:
        return os.path.commonpath([base_path, candidate_path]) == base_path
    except ValueError:
        return False


def decode_escaped_path(value: str) -> str:
    decoded = str(value or "").strip()
    if not decoded:
        return ""
    return (
        decoded.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )
