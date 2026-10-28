"""SoAI - Backend lifecycle prerequisite, contention and cleanup errors [backend/core/errors/backend_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import (
    ProcessError,
    ServiceUnavailableError,
    StateError,
    ValidationError,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "BackendPrerequisiteError",
    "IpcCancellationCleanupError",
    "NativeProbeTerminationError",
    "PluginLifecycleLockContentionError",
    "backend_prerequisite_message",
)

BACKEND_PREREQUISITE_MESSAGES: tuple[tuple[str, str], ...] = (
    (
        "backend_docker_cli_missing",
        "Docker is not installed or is unavailable to the backend account. Install Docker and retry.",
    ),
    (
        "backend_docker_engine_unavailable",
        "The backend account cannot access the Docker engine. Start Docker and check account permissions and virtualization support, then retry.",
    ),
    (
        "backend_docker_buildx_unavailable",
        "Docker Buildx is unavailable to the backend account. Install or enable Buildx, then retry.",
    ),
    (
        "backend_docker_builder_unavailable",
        "The Docker Buildx builder is unavailable to the backend account. Configure a working builder and retry.",
    ),
    (
        "backend_docker_storage_unavailable",
        "The backend account could not discover Docker storage. Start Docker, confirm the backend account can query the engine, then retry.",
    ),
    (
        "backend_docker_storage_unmapped",
        "Docker storage cannot be mapped to a verified host location. Use a local Docker engine whose data disk is on a local drive, then retry.",
    ),
    (
        "backend_docker_storage_access_denied",
        "The backend account cannot inspect the Docker storage location. Check its access to the Docker data location, then retry.",
    ),
    (
        "backend_docker_storage_changed",
        "The Docker engine or its storage changed during installation. Keep Docker settings unchanged while installing, then retry.",
    ),
)


def backend_prerequisite_message(code: str | int) -> str | None:
    return next(
        (message for error_code, message in BACKEND_PREREQUISITE_MESSAGES if error_code == code),
        None,
    )


class BackendPrerequisiteError(StateError):
    def __init__(self, code: str, *, details: Mapping[str, JSONValue] | None = None) -> None:
        message = backend_prerequisite_message(code)
        if message is None:
            raise ValidationError("Backend prerequisite code is invalid.")
        super().__init__(code, details=details)
        self.message = message
        self.code = code
        self.public_message = message

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.code,), {"details": self.details})


class PluginLifecycleLockContentionError(ServiceUnavailableError):
    code: str | int = "plugin_lifecycle_locked"
    public_message: str | None = (
        "Another backend operation owns this plugin. Wait for it to finish and retry."
    )


class IpcCancellationCleanupError(StateError):
    code: str | int = "ipc_cancellation_cleanup_failed"
    public_message: str | None = (
        "The worker did not confirm cancellation cleanup. Restart the affected service and retry."
    )


class NativeProbeTerminationError(ProcessError):
    public_message: str | None = (
        "The backend runtime check could not be stopped. Restart SoAI before retrying."
    )
