"""SoAI - Docker endpoint and daemon identity inspection [backend/core/system/docker_storage/daemon.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.system.commands import run_argv_capture
from core.system.docker_storage.location import (
    DOCKER_CLI_MISSING,
    DOCKER_ENGINE_UNAVAILABLE,
    DOCKER_STORAGE_UNAVAILABLE,
    DOCKER_STORAGE_UNMAPPED,
    reject_docker_storage,
)
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DockerDaemonIdentity",
    "inspect_docker_daemon",
    "resolve_docker_endpoint",
)

_PERMISSION_DENIED_MARKERS = ("permission denied", "access is denied")
_LOCAL_ENDPOINT_SCHEMES = ("unix://", "npipe://")
_COMMAND_UNAVAILABLE_RETURN_CODE = 127


@dataclass(frozen=True, slots=True)
class DockerDaemonIdentity:
    endpoint: str
    daemon_id: str
    name: str
    os_type: str
    operating_system: str
    kernel_version: str
    root_directory: str


def resolve_docker_endpoint() -> str:
    endpoint_output = _run_docker(
        ("docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"),
        reason="endpoint",
    )
    try:
        endpoint = parse_json_value(endpoint_output, field="docker endpoint")
    except ValidationError:
        endpoint = None
    if not isinstance(endpoint, str) or not endpoint.strip() or endpoint != endpoint.strip():
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "endpoint_malformed")
    if not endpoint.lower().startswith(_LOCAL_ENDPOINT_SCHEMES):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "endpoint_not_local")
    return endpoint


def inspect_docker_daemon(endpoint: str) -> DockerDaemonIdentity:
    info_output = _run_docker(
        ("docker", "--host", endpoint, "info", "--format", "{{json .}}"),
        reason="daemon",
    )
    try:
        info = parse_json_dict(info_output, field="docker info")
    except ValidationError:
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "daemon_info_malformed")
    return DockerDaemonIdentity(
        endpoint=endpoint,
        daemon_id=_require_text(info, "ID"),
        name=_require_text(info, "Name"),
        os_type=_require_text(info, "OSType"),
        operating_system=_require_text(info, "OperatingSystem"),
        kernel_version=_require_text(info, "KernelVersion"),
        root_directory=_require_text(info, "DockerRootDir"),
    )


def _run_docker(argv: tuple[str, ...], *, reason: str) -> str:
    result = run_argv_capture(argv, timeout=INTERACTIVE_TIMEOUT_SEC)
    if result.return_code == 0:
        return result.stdout
    if result.return_code == _COMMAND_UNAVAILABLE_RETURN_CODE:
        reject_docker_storage(DOCKER_CLI_MISSING, "docker_cli_unavailable")
    diagnostic = result.stderr.lower()
    if any(marker in diagnostic for marker in _PERMISSION_DENIED_MARKERS):
        reject_docker_storage(DOCKER_ENGINE_UNAVAILABLE, f"{reason}_access_denied")
    reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, f"{reason}_query_failed")


def _require_text(payload: JSONDict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "daemon_info_incomplete")
    return value.strip()
