"""SoAI - Saved timeout default upgrade completion state [backend/app/updater/config_timeout_default_upgrade_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.errors.exceptions import StateError
from core.filesystem.atomic_writes import (
    atomic_create_text_content_exclusive,
    atomic_write_text_content,
)
from core.filesystem.open_files import read_regular_file_no_symlink

__all__ = (
    "begin_timeout_default_upgrade",
    "complete_pending_timeout_default_upgrade",
    "mark_timeout_default_upgrade_completed",
    "timeout_default_upgrade_marker_path",
    "timeout_default_upgrade_completed",
)

_TIMEOUT_DEFAULT_UPGRADE_MARKER_SUFFIX = ".timeout-default-upgrade-complete"
_TIMEOUT_DEFAULT_UPGRADE_PENDING_CONTENT = "pending\n"
_TIMEOUT_DEFAULT_UPGRADE_MARKER_CONTENT = "complete\n"


def timeout_default_upgrade_marker_path(config_path: str) -> str:
    return f"{config_path}{_TIMEOUT_DEFAULT_UPGRADE_MARKER_SUFFIX}"


def _read_timeout_default_upgrade_marker(config_path: str) -> str | None:
    marker_path = timeout_default_upgrade_marker_path(config_path)
    secure_runtime_config_paths(config_path, marker_path)
    if not os.path.lexists(marker_path):
        return None
    marker_content = read_regular_file_no_symlink(marker_path, max_bytes=128).replace(
        b"\r\n", b"\n"
    )
    if marker_content not in (
        _TIMEOUT_DEFAULT_UPGRADE_PENDING_CONTENT.encode("ascii"),
        _TIMEOUT_DEFAULT_UPGRADE_MARKER_CONTENT.encode("ascii"),
    ):
        raise StateError("Saved timeout default upgrade marker is invalid.")
    return marker_content.decode("ascii")


def timeout_default_upgrade_completed(config_path: str) -> bool:
    marker_content = _read_timeout_default_upgrade_marker(config_path)
    return marker_content == _TIMEOUT_DEFAULT_UPGRADE_MARKER_CONTENT


def begin_timeout_default_upgrade(config_path: str) -> None:
    marker_path = timeout_default_upgrade_marker_path(config_path)
    marker_content = _read_timeout_default_upgrade_marker(config_path)
    if marker_content is not None:
        return
    secure_runtime_config_paths(config_path, marker_path)
    try:
        atomic_create_text_content_exclusive(
            marker_path,
            _TIMEOUT_DEFAULT_UPGRADE_PENDING_CONTENT,
            encoding="utf-8",
            errors="strict",
            fsync=True,
            file_mode=runtime_config_atomic_file_mode(),
            fsync_parent_directory=True,
        )
    except FileExistsError as file_exists_error:
        if _read_timeout_default_upgrade_marker(config_path) is None:
            raise StateError(
                "Saved timeout default upgrade marker disappeared unexpectedly."
            ) from file_exists_error


def mark_timeout_default_upgrade_completed(config_path: str) -> None:
    marker_path = timeout_default_upgrade_marker_path(config_path)
    marker_content = _read_timeout_default_upgrade_marker(config_path)
    if marker_content == _TIMEOUT_DEFAULT_UPGRADE_MARKER_CONTENT:
        return
    if marker_content != _TIMEOUT_DEFAULT_UPGRADE_PENDING_CONTENT:
        raise StateError("Saved timeout default upgrade was not marked pending.")
    atomic_write_text_content(
        marker_path,
        _TIMEOUT_DEFAULT_UPGRADE_MARKER_CONTENT,
        encoding="utf-8",
        errors="strict",
        fsync=True,
        file_mode=runtime_config_atomic_file_mode(),
        fsync_parent_directory=True,
    )


def complete_pending_timeout_default_upgrade(config_path: str) -> None:
    if (
        _read_timeout_default_upgrade_marker(config_path)
        == _TIMEOUT_DEFAULT_UPGRADE_PENDING_CONTENT
    ):
        mark_timeout_default_upgrade_completed(config_path)
