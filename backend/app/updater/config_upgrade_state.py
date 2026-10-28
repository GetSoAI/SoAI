"""SoAI - Saved configuration upgrade completion state [backend/app/updater/config_upgrade_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from enum import Enum

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
    "SavedConfigUpgrade",
    "begin_config_upgrade",
    "complete_pending_config_upgrades",
    "config_upgrade_completed",
    "config_upgrade_marker_path",
    "mark_config_upgrade_completed",
)

_PENDING_CONTENT = "pending\n"
_COMPLETE_CONTENT = "complete\n"


class SavedConfigUpgrade(Enum):
    TIMEOUT_DEFAULT = ("Saved timeout default upgrade", ".timeout-default-upgrade-complete")
    WINDOWS_SERVICE_PATHS = (
        "Saved Windows service path upgrade",
        ".windows-service-path-upgrade-complete",
    )

    @property
    def description(self) -> str:
        return self.value[0]

    @property
    def marker_suffix(self) -> str:
        return self.value[1]


def config_upgrade_marker_path(config_path: str, upgrade: SavedConfigUpgrade) -> str:
    return f"{config_path}{upgrade.marker_suffix}"


def _read_config_upgrade_marker(config_path: str, upgrade: SavedConfigUpgrade) -> str | None:
    marker_path = config_upgrade_marker_path(config_path, upgrade)
    secure_runtime_config_paths(config_path, marker_path)
    if not os.path.lexists(marker_path):
        return None
    marker_content = read_regular_file_no_symlink(marker_path, max_bytes=128).replace(
        b"\r\n", b"\n"
    )
    if marker_content not in (
        _PENDING_CONTENT.encode("ascii"),
        _COMPLETE_CONTENT.encode("ascii"),
    ):
        raise StateError(f"{upgrade.description} marker is invalid.")
    return marker_content.decode("ascii")


def config_upgrade_completed(config_path: str, upgrade: SavedConfigUpgrade) -> bool:
    return _read_config_upgrade_marker(config_path, upgrade) == _COMPLETE_CONTENT


def begin_config_upgrade(config_path: str, upgrade: SavedConfigUpgrade) -> None:
    marker_path = config_upgrade_marker_path(config_path, upgrade)
    if _read_config_upgrade_marker(config_path, upgrade) is not None:
        return
    secure_runtime_config_paths(config_path, marker_path)
    try:
        atomic_create_text_content_exclusive(
            marker_path,
            _PENDING_CONTENT,
            encoding="utf-8",
            errors="strict",
            fsync=True,
            file_mode=runtime_config_atomic_file_mode(),
            fsync_parent_directory=True,
        )
    except FileExistsError as file_exists_error:
        if _read_config_upgrade_marker(config_path, upgrade) is None:
            raise StateError(
                f"{upgrade.description} marker disappeared unexpectedly."
            ) from file_exists_error


def mark_config_upgrade_completed(config_path: str, upgrade: SavedConfigUpgrade) -> None:
    marker_path = config_upgrade_marker_path(config_path, upgrade)
    marker_content = _read_config_upgrade_marker(config_path, upgrade)
    if marker_content == _COMPLETE_CONTENT:
        return
    if marker_content != _PENDING_CONTENT:
        raise StateError(f"{upgrade.description} was not marked pending.")
    atomic_write_text_content(
        marker_path,
        _COMPLETE_CONTENT,
        encoding="utf-8",
        errors="strict",
        fsync=True,
        file_mode=runtime_config_atomic_file_mode(),
        fsync_parent_directory=True,
    )


def complete_pending_config_upgrades(config_path: str) -> None:
    for upgrade in SavedConfigUpgrade:
        if _read_config_upgrade_marker(config_path, upgrade) == _PENDING_CONTENT:
            mark_config_upgrade_completed(config_path, upgrade)
