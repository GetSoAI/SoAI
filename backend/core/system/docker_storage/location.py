"""SoAI - Resolved Docker storage location and host path observations [backend/core/system/docker_storage/location.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NoReturn

from core.errors.backend_lifecycle import BackendPrerequisiteError
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.windows_remote_paths import is_windows_remote_or_unmapped_path

if TYPE_CHECKING:
    type DockerStorageType = Literal["native_directory", "desktop_virtual_disk"]

__all__ = (
    "DOCKER_CLI_MISSING",
    "DOCKER_ENGINE_UNAVAILABLE",
    "DOCKER_STORAGE_ACCESS_DENIED",
    "DOCKER_STORAGE_CHANGED",
    "DOCKER_STORAGE_UNAVAILABLE",
    "DOCKER_STORAGE_UNMAPPED",
    "DockerStorageLocation",
    "HostPathObservation",
    "observe_host_path",
    "reject_docker_storage",
)

DOCKER_CLI_MISSING = "backend_docker_cli_missing"
DOCKER_ENGINE_UNAVAILABLE = "backend_docker_engine_unavailable"
DOCKER_STORAGE_UNAVAILABLE = "backend_docker_storage_unavailable"
DOCKER_STORAGE_UNMAPPED = "backend_docker_storage_unmapped"
DOCKER_STORAGE_ACCESS_DENIED = "backend_docker_storage_access_denied"
DOCKER_STORAGE_CHANGED = "backend_docker_storage_changed"


@dataclass(frozen=True, slots=True)
class DockerStorageLocation:
    endpoint: str
    daemon_id: str
    daemon_os_type: str
    storage_type: DockerStorageType
    host_storage_path: str
    host_storage_identity: tuple[int, int]
    backing_image_path: str | None
    backing_image_identity: tuple[int, int] | None

    def docker_command(self, *arguments: str) -> tuple[str, ...]:
        return ("docker", "--host", self.endpoint, *arguments)


@dataclass(frozen=True, slots=True)
class HostPathObservation:
    real_path: str
    is_directory: bool
    is_regular_file: bool
    is_reparse_point: bool
    is_remote: bool
    identity: tuple[int, int]


def reject_docker_storage(code: str, reason: str) -> NoReturn:
    raise BackendPrerequisiteError(code, details={"reason": reason})


def observe_host_path(path: str) -> HostPathObservation | None:
    try:
        link_status = os.lstat(path)
        real_path = os.path.realpath(path)
        target_status = os.stat(real_path)
    except PermissionError:
        reject_docker_storage(DOCKER_STORAGE_ACCESS_DENIED, "host_path_access_denied")
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "host_path_inspection_failed")
    return HostPathObservation(
        real_path=real_path,
        is_directory=stat.S_ISDIR(link_status.st_mode),
        is_regular_file=stat.S_ISREG(link_status.st_mode),
        is_reparse_point=stat.S_ISLNK(link_status.st_mode) or is_windows_reparse_point(link_status),
        is_remote=is_windows_remote_or_unmapped_path(real_path),
        identity=(int(target_status.st_dev), int(target_status.st_ino)),
    )
