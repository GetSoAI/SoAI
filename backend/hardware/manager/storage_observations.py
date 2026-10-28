"""SoAI - Storage row observation identity and retention [backend/hardware/manager/storage_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue

__all__ = (
    "disk_rows",
    "disk_identity",
    "disk_has_strong_identity",
    "retained_disk_row",
    "reconcile_disk_rows",
)


def disk_rows(value: JSONValue, validate_status: Callable[[JSONDict], None]) -> list[JSONDict]:
    if not isinstance(value, list):
        raise ValidationError("Hardware storage list is invalid.")
    rows: list[JSONDict] = []
    identities: set[tuple[str, str]] = set()
    for row in value:
        if not isinstance(row, dict):
            raise ValidationError("Hardware storage row is invalid.")
        status = row.get("observation_status")
        identity = disk_identity(row)
        if "observation_status" in row:
            if not isinstance(status, dict) or identity is None:
                raise ValidationError("Hardware storage observation identity is invalid.")
            validate_status(status)
        if identity is not None:
            if identity in identities:
                raise ValidationError("Hardware storage observation identity is duplicated.")
            identities.add(identity)
        rows.append(row)
    return rows


def disk_identity(row: JSONDict) -> tuple[str, str] | None:
    device_id, mount = row.get("device_id"), row.get("mount")
    if isinstance(device_id, str) and device_id.strip() and isinstance(mount, str):
        return device_id, mount
    return None


def disk_has_strong_identity(row: JSONDict) -> bool:
    return any(
        isinstance(row.get(key), str) and bool(row[key])
        for key in ("uuid", "ptuuid", "wwn", "serial")
    )


def retained_disk_row(row: JSONDict, previous_status: JSONDict, checked_at_ms: int) -> JSONDict:
    retained = deepcopy(row)
    status = retained.get("observation_status")
    if not isinstance(status, dict):
        status = deepcopy(previous_status)
    status["status"] = "stale"
    status["sampled_current"] = False
    status["checked_at_ms"] = checked_at_ms
    if "observed_at_ms" not in status:
        status["observed_at_ms"] = None
    retained["observation_status"] = status
    return retained


def reconcile_disk_rows(
    value: JSONValue,
    previous_value: JSONValue,
    candidate: JSONDict,
    previous_status: JSONDict,
    validate_status: Callable[[JSONDict], None],
) -> list[JSONDict]:
    incoming = disk_rows(value, validate_status)
    previous = disk_rows(previous_value, validate_status)
    checked = candidate["checked_at_ms"]
    if not isinstance(checked, int):
        raise ValidationError("Hardware storage check timestamp is invalid.")
    diagnostics = candidate.get("diagnostics")
    diagnostic_rows = diagnostics if isinstance(diagnostics, list) else []
    incomplete_sources = {
        scope
        for item in diagnostic_rows
        if isinstance(item, dict)
        and isinstance(scope := item.get("scope"), str)
        and scope in ("partitions", "block_metadata", "zfs")
    }
    malformed_identity = any(
        isinstance(item, dict) and item.get("reason") == "malformed_identity"
        for item in diagnostic_rows
    )
    accepted_rows: dict[tuple[str, str], JSONDict] = {}
    ambiguous: set[tuple[str, str]] = set()
    for row in incoming:
        identity = disk_identity(row)
        if identity is None:
            continue
        conflicts = [
            old
            for old in previous
            if disk_identity(old) != identity
            and old.get("filesystem") == row.get("filesystem")
            and old.get("mount") == row.get("mount")
            and disk_has_strong_identity(old)
        ]
        if conflicts and not disk_has_strong_identity(row):
            ambiguous.update(key for old in conflicts if (key := disk_identity(old)) is not None)
            diagnostic_rows = [
                *diagnostic_rows,
                {"scope": "item", "reason": "identity_unavailable"},
            ]
            candidate["diagnostics"] = diagnostic_rows
            candidate["status"] = "partial"
            continue
        status = row.get("observation_status")
        if isinstance(status, dict) and status["status"] not in ("available", "partial"):
            old = next((old for old in previous if disk_identity(old) == identity), None)
            if old is not None:
                accepted_rows[identity] = retained_disk_row(old, previous_status, checked)
            continue
        fresh = deepcopy(row)
        if isinstance(status, dict):
            fresh_status = deepcopy(status)
        else:
            fresh_status = {
                "status": "available",
                "observed_at_ms": candidate["observed_at_ms"],
                "checked_at_ms": checked,
            }
            if "sampled_current" in candidate:
                fresh_status["sampled_current"] = candidate["sampled_current"]
        fresh["observation_status"] = fresh_status
        accepted_rows[identity] = fresh
    result: list[JSONDict] = []
    for old in previous:
        identity = disk_identity(old)
        if identity in accepted_rows:
            result.append(accepted_rows.pop(identity))
        elif identity is not None:
            replaced = any(
                disk_has_strong_identity(row)
                and disk_identity(row) != identity
                and row.get("filesystem") == old.get("filesystem")
                and row.get("mount") == old.get("mount")
                for row in incoming
            )
            is_zfs = old.get("fstype") == "zfs" or old.get("storage_backend") == "zfs"
            incomplete_membership = (
                malformed_identity
                or "block_metadata" in incomplete_sources
                or ("partitions" in incomplete_sources and not is_zfs)
                or ("zfs" in incomplete_sources and is_zfs)
            )
            if identity in ambiguous or (incomplete_membership and not replaced):
                result.append(retained_disk_row(old, previous_status, checked))
    result.extend(accepted_rows.values())
    result.extend(deepcopy(row) for row in incoming if disk_identity(row) is None)
    return result
