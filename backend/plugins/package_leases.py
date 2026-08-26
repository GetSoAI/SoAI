"""SoAI - Identity-verified plugin package cache leases [backend/plugins/package_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.record_fields import require_int, require_non_empty_str
from plugins.package_paths import get_plugin_package_lease_directory

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "PluginPackageLease",
    "create_plugin_package_lease",
    "list_live_plugin_package_leases",
    "read_pid_create_time_ms",
    "remove_plugin_package_lease",
)

LOGGER_NAME = "SoAI.plugins.package_leases"
OPERATION_INVALID_LEASE = "plugins.package_leases.remove_invalid"
LEASE_RECORD_FIELDS = frozenset(
    {
        "archiveHash",
        "createTimeMs",
        "pid",
        "pluginName",
        "workerId",
    }
)


@dataclass(frozen=True, slots=True)
class PluginPackageLease:
    plugin_name: str
    archive_hash: str
    worker_id: int
    pid: int
    create_time_ms: int


def read_pid_create_time_ms(pid: int) -> int | None:
    try:
        return read_process_create_time_ms(psutil.Process(pid))
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def _lease_payload(lease: PluginPackageLease) -> dict[str, str | int]:
    return {
        "archiveHash": lease.archive_hash,
        "createTimeMs": lease.create_time_ms,
        "pid": lease.pid,
        "pluginName": lease.plugin_name,
        "workerId": lease.worker_id,
    }


def _lease_filename(lease: PluginPackageLease) -> str:
    return f"{lease.worker_id}-{lease.pid}-{lease.create_time_ms}.json"


def create_plugin_package_lease(
    *,
    temp_directory: str,
    lease: PluginPackageLease,
    storage_manager: StorageManagerProtocol,
) -> str:
    try:
        require_canonical_sha256_hexdigest(
            lease.archive_hash,
            label="Plugin package lease archive hash",
        )
    except StateError as exception:
        raise ValidationError(
            "Plugin package lease archive hash must be lowercase SHA-256."
        ) from exception
    lease_directory = get_plugin_package_lease_directory(temp_directory, lease.plugin_name)
    leases_root = os.path.dirname(lease_directory)
    if os.path.islink(leases_root) or (
        os.path.lexists(leases_root) and not os.path.isdir(leases_root)
    ):
        remove_plugin_package_lease(leases_root)
    os.makedirs(leases_root, exist_ok=True)
    if os.path.islink(lease_directory) or (
        os.path.lexists(lease_directory) and not os.path.isdir(lease_directory)
    ):
        remove_plugin_package_lease(lease_directory)
    os.makedirs(lease_directory, exist_ok=True)
    lease_path = os.path.join(lease_directory, _lease_filename(lease))
    content = serialize_json_compact_stable_strict(_lease_payload(lease), ensure_ascii=True)
    required_bytes = len(content.encode("utf-8"))
    with storage_manager.reserve_disk_space(
        path=lease_directory,
        required_bytes=required_bytes,
        operation="plugins.package_leases.create",
        details={
            "plugin_name": lease.plugin_name,
            "archive_hash": lease.archive_hash,
            "worker_id": lease.worker_id,
            "required_bytes": required_bytes,
        },
    ) as reservation:
        with claim_reserved_write(reservation, size_bytes=required_bytes):
            atomic_write_text_content(
                lease_path,
                content,
                ensure_parent=False,
                file_mode=0o600,
                fsync_parent_directory=True,
            )
    return lease_path


def remove_plugin_package_lease(lease_path: str) -> None:
    try:
        if os.path.isdir(lease_path) and not os.path.islink(lease_path):
            shutil.rmtree(lease_path)
        else:
            os.unlink(lease_path)
    except FileNotFoundError:
        get_logger(LOGGER_NAME).debug("Plugin package lease was already absent: %s", lease_path)


def _parse_lease(lease_path: str) -> PluginPackageLease:
    raw = read_regular_file_no_symlink(
        lease_path,
        max_bytes=4096,
        not_found_message="Plugin package lease was not found.",
        symlink_message="Plugin package lease must not be a symbolic link.",
        open_message="Plugin package lease could not be opened.",
        inspect_message="Plugin package lease could not be inspected.",
        regular_file_message="Plugin package lease must be a regular file.",
    )
    if len(raw) > 4096:
        raise ValidationError("Plugin package lease exceeds 4096 bytes.")
    payload = parse_json_dict(raw, field="plugin package lease")
    if set(payload) != LEASE_RECORD_FIELDS:
        raise ValidationError("Plugin package lease fields are invalid.")
    plugin_name = require_non_empty_str(
        payload.get("pluginName"),
        label="pluginName",
        build_error=ValidationError,
    )
    archive_hash = require_non_empty_str(
        payload.get("archiveHash"),
        label="archiveHash",
        build_error=ValidationError,
    )
    try:
        require_canonical_sha256_hexdigest(
            archive_hash,
            label="Plugin package lease archiveHash",
        )
    except StateError as exception:
        raise ValidationError("Plugin package lease archiveHash is invalid.") from exception
    worker_id = require_int(
        payload.get("workerId"),
        label="workerId",
        build_error=ValidationError,
        minimum=1,
    )
    pid = require_int(
        payload.get("pid"),
        label="pid",
        build_error=ValidationError,
        minimum=1,
    )
    create_time_ms = require_int(
        payload.get("createTimeMs"),
        label="createTimeMs",
        build_error=ValidationError,
        minimum=1,
    )
    return PluginPackageLease(
        plugin_name=plugin_name,
        archive_hash=archive_hash,
        worker_id=worker_id,
        pid=pid,
        create_time_ms=create_time_ms,
    )


def list_live_plugin_package_leases(
    temp_directory: str,
    plugin_name: str,
) -> list[PluginPackageLease]:
    lease_directory = get_plugin_package_lease_directory(temp_directory, plugin_name)
    leases_root = os.path.dirname(lease_directory)
    if os.path.islink(leases_root) or (
        os.path.lexists(leases_root) and not os.path.isdir(leases_root)
    ):
        remove_plugin_package_lease(leases_root)
        return []
    if os.path.islink(lease_directory) or (
        os.path.lexists(lease_directory) and not os.path.isdir(lease_directory)
    ):
        remove_plugin_package_lease(lease_directory)
        return []
    try:
        filenames = sorted(os.listdir(lease_directory))
    except FileNotFoundError:
        return []
    live_leases: list[PluginPackageLease] = []
    for filename in filenames:
        lease_path = os.path.join(lease_directory, filename)
        try:
            lease = _parse_lease(lease_path)
        except (OSError, ValidationError) as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Invalid plugin package lease removed during cache inspection (non-critical).",
                operation=OPERATION_INVALID_LEASE,
                details={"plugin_name": plugin_name, "lease_path": lease_path},
                level="warning",
            )
            remove_plugin_package_lease(lease_path)
            continue
        if lease.plugin_name != plugin_name:
            remove_plugin_package_lease(lease_path)
            continue
        current_create_time_ms = read_pid_create_time_ms(lease.pid)
        if current_create_time_ms != lease.create_time_ms:
            remove_plugin_package_lease(lease_path)
            continue
        live_leases.append(lease)
    return live_leases
