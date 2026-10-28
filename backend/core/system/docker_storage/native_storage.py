"""SoAI - Host-native Docker daemon storage validation [backend/core/system/docker_storage/native_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ntpath
import platform
import posixpath
import socket

from core.platform.os import is_linux, is_windows
from core.system.docker_storage.daemon import DockerDaemonIdentity
from core.system.docker_storage.location import (
    DOCKER_STORAGE_UNMAPPED,
    DockerStorageLocation,
    observe_host_path,
    reject_docker_storage,
)

__all__ = (
    "DOCKER_DESKTOP_OPERATING_SYSTEM",
    "resolve_native_docker_storage",
)

DOCKER_DESKTOP_OPERATING_SYSTEM = "Docker Desktop"


def resolve_native_docker_storage(daemon: DockerDaemonIdentity) -> DockerStorageLocation:
    if is_linux():
        _require_native_linux_daemon(daemon)
        absolute = posixpath.isabs(daemon.root_directory)
    elif is_windows():
        _require_native_windows_daemon(daemon)
        absolute = ntpath.isabs(daemon.root_directory)
    else:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "host_platform_unsupported")
    if not absolute:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "root_directory_not_host_path")
    observation = observe_host_path(daemon.root_directory)
    if observation is None or not observation.is_directory:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "root_directory_missing")
    if observation.is_remote:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "root_directory_remote")
    return DockerStorageLocation(
        endpoint=daemon.endpoint,
        daemon_id=daemon.daemon_id,
        daemon_os_type=daemon.os_type,
        storage_type="native_directory",
        host_storage_path=observation.real_path,
        host_storage_identity=observation.identity,
        backing_image_path=None,
        backing_image_identity=None,
    )


def _require_native_linux_daemon(daemon: DockerDaemonIdentity) -> None:
    if not daemon.endpoint.startswith("unix://"):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "endpoint_not_local_socket")
    if daemon.os_type != "linux" or daemon.operating_system == DOCKER_DESKTOP_OPERATING_SYSTEM:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "daemon_runs_in_virtual_machine")
    if daemon.kernel_version != platform.release() or daemon.name != socket.gethostname():
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "daemon_host_differs")


def _require_native_windows_daemon(daemon: DockerDaemonIdentity) -> None:
    if not daemon.endpoint.lower().startswith("npipe:////./pipe/"):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "endpoint_not_local_pipe")
    if daemon.os_type != "windows":
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "daemon_runs_in_virtual_machine")
    if daemon.name.casefold() != socket.gethostname().casefold():
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "daemon_host_differs")
