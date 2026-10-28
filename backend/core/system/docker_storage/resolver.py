"""SoAI - Bounded Docker storage resolution and admission revalidation [backend/core/system/docker_storage/resolver.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.platform.os import is_windows
from core.system.docker_storage.daemon import inspect_docker_daemon, resolve_docker_endpoint
from core.system.docker_storage.location import (
    DOCKER_STORAGE_CHANGED,
    DockerStorageLocation,
    reject_docker_storage,
)
from core.system.docker_storage.native_storage import resolve_native_docker_storage
from core.system.docker_storage.windows_desktop_host import build_windows_desktop_storage_host
from core.system.docker_storage.windows_desktop_storage import map_windows_desktop_storage

__all__ = (
    "resolve_docker_storage",
    "revalidate_docker_storage",
)


async def resolve_docker_storage() -> DockerStorageLocation:
    return await run_joined_thread_call(
        _resolve_docker_storage_now,
        task_name="docker-storage-resolution",
        retain_resources_until_complete=True,
    )


async def revalidate_docker_storage(admitted: DockerStorageLocation) -> DockerStorageLocation:
    current = await resolve_docker_storage()
    if current != admitted:
        reject_docker_storage(DOCKER_STORAGE_CHANGED, "storage_identity_changed")
    return current


def _resolve_docker_storage_now() -> DockerStorageLocation:
    daemon = inspect_docker_daemon(resolve_docker_endpoint())
    if is_windows() and daemon.os_type == "linux":
        return map_windows_desktop_storage(daemon, build_windows_desktop_storage_host())
    return resolve_native_docker_storage(daemon)
