"""SoAI - Durable OS storage mutation admission builders [backend/features/api/runtime/storage_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict
from core.validation.requirements import require_nonempty_str
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "build_fstab_add_mutation_admission",
    "build_fstab_remove_mutation_admission",
    "build_mount_mutation_admission",
    "build_partition_create_mutation_admission",
    "build_partition_format_mutation_admission",
    "build_unmount_mutation_admission",
)

FSTAB_CONFLICT_KEY = "os_storage:fstab"


def _canonical_path(value: str, *, field: str) -> str:
    normalized = os.path.normpath(require_nonempty_str(value, field=field))
    if not normalized.startswith(os.sep):
        raise ValidationError(f"{field} must be an absolute path.")
    return normalized


def _draft(
    *,
    request_id: str,
    operation_type: str,
    target_identity: str,
    conflict_keys: tuple[str, ...],
    payload: JSONDict,
    supersedes_request_id: str | None = None,
) -> MutationAdmissionDraft:
    return MutationAdmissionDraft(
        request_id=require_mutation_request_id(request_id),
        conflict_keys=tuple(sorted(set(conflict_keys))),
        shared_conflict_keys=(),
        operation_type=operation_type,
        target_identity=target_identity,
        authorization_scope="host_management_admin",
        command_payload=serialize_json_compact_stable(payload),
        schema_discriminator=f"{operation_type}_v1",
        supersedes_request_id=supersedes_request_id,
    )


def build_mount_mutation_admission(
    *,
    request_id: str,
    device_path: str,
    partition_path: str,
    mount_point: str,
) -> MutationAdmissionDraft:
    device = _canonical_path(device_path, field="device_path")
    partition = _canonical_path(partition_path, field="partition_path")
    mount = _canonical_path(mount_point, field="mount_point")
    return _draft(
        request_id=request_id,
        operation_type="os_storage_mount",
        target_identity=partition,
        conflict_keys=(
            f"os_storage:device:{device}",
            f"os_storage:partition:{partition}",
            f"os_storage:mountpoint:{mount}",
        ),
        payload={
            "device_path": device,
            "partition_path": partition,
            "mount_point": mount,
        },
    )


def build_unmount_mutation_admission(
    *,
    request_id: str,
    device_path: str,
    partition_path: str,
) -> MutationAdmissionDraft:
    device = _canonical_path(device_path, field="device_path")
    partition = _canonical_path(partition_path, field="partition_path")
    return _draft(
        request_id=request_id,
        operation_type="os_storage_unmount",
        target_identity=partition,
        conflict_keys=(
            FSTAB_CONFLICT_KEY,
            f"os_storage:device:{device}",
            f"os_storage:partition:{partition}",
        ),
        payload={"device_path": device, "partition_path": partition},
    )


def build_fstab_add_mutation_admission(
    *,
    request_id: str,
    device_path: str,
    partition_path: str,
    uuid: str,
    mount_point: str,
    filesystem: str,
) -> MutationAdmissionDraft:
    device = _canonical_path(device_path, field="device_path")
    partition = _canonical_path(partition_path, field="partition_path")
    uuid_value = require_nonempty_str(uuid, field="uuid")
    normalized_uuid = uuid_value.lower()
    mount = _canonical_path(mount_point, field="mount_point")
    normalized_filesystem = require_nonempty_str(filesystem, field="filesystem")
    return _draft(
        request_id=request_id,
        operation_type="os_storage_fstab_add",
        target_identity=mount,
        conflict_keys=(
            FSTAB_CONFLICT_KEY,
            f"os_storage:device:{device}",
            f"os_storage:mountpoint:{mount}",
            f"os_storage:partition:{partition}",
            f"os_storage:uuid:{normalized_uuid}",
        ),
        payload={
            "uuid": uuid_value,
            "device_path": device,
            "partition_path": partition,
            "mount_point": mount,
            "filesystem": normalized_filesystem,
        },
    )


def build_fstab_remove_mutation_admission(
    *,
    request_id: str,
    mount_point: str,
) -> MutationAdmissionDraft:
    mount = _canonical_path(mount_point, field="mount_point")
    return _draft(
        request_id=request_id,
        operation_type="os_storage_fstab_remove",
        target_identity=mount,
        conflict_keys=(FSTAB_CONFLICT_KEY, f"os_storage:mountpoint:{mount}"),
        payload={"mount_point": mount},
    )


def build_partition_create_mutation_admission(
    *,
    request_id: str,
    device_path: str,
    device_fingerprint: str,
    start: str,
    end: str,
    filesystem: str | None,
    partition_name: str | None,
) -> MutationAdmissionDraft:
    device = _canonical_path(device_path, field="device_path")
    fingerprint = require_nonempty_str(device_fingerprint, field="device_fingerprint")
    start_value = require_nonempty_str(start, field="start")
    end_value = require_nonempty_str(end, field="end")
    payload: JSONDict = {
        "device_path": device,
        "device_fingerprint": fingerprint,
        "start": start_value,
        "end": end_value,
        "filesystem": coerce_optional_trimmed_str(filesystem),
        "partition_name": coerce_optional_trimmed_str(partition_name),
    }
    return _draft(
        request_id=request_id,
        operation_type="os_storage_partition_create",
        target_identity=device,
        conflict_keys=(f"os_storage:device:{device}",),
        payload=payload,
    )


def build_partition_format_mutation_admission(
    *,
    request_id: str,
    device_path: str,
    partition_path: str,
    device_fingerprint: str,
    filesystem: str,
    label: str | None,
    allow_wipe: bool,
    recovery_request_id: str | None = None,
) -> MutationAdmissionDraft:
    device = _canonical_path(device_path, field="device_path")
    partition = _canonical_path(partition_path, field="partition_path")
    if partition == device:
        raise ValidationError("partition_path must identify a partition.")
    fingerprint = require_nonempty_str(device_fingerprint, field="device_fingerprint")
    filesystem_value = require_nonempty_str(filesystem, field="filesystem")
    recovery_id = (
        require_mutation_request_id(recovery_request_id)
        if recovery_request_id is not None
        else None
    )
    payload: JSONDict = {
        "device_path": device,
        "partition_path": partition,
        "device_fingerprint": fingerprint,
        "filesystem": filesystem_value,
        "label": coerce_optional_trimmed_str(label),
        "allow_wipe": allow_wipe,
    }
    if recovery_id is not None:
        payload["recovery_request_id"] = recovery_id
    return _draft(
        request_id=request_id,
        operation_type="os_storage_partition_format",
        target_identity=partition,
        conflict_keys=(
            f"os_storage:device:{device}",
            f"os_storage:partition:{partition}",
        ),
        payload=payload,
        supersedes_request_id=recovery_id,
    )
