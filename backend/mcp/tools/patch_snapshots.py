"""SoAI - MCP apply_patch file snapshot and rollback helpers [backend/mcp/tools/patch_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from mcp.tools.patch_types import (
    AddOperation,
    DeleteOperation,
    FileSnapshot,
    UpdateOperation,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "build_file_snapshots",
    "collect_touched_paths",
    "restore_file_snapshots",
)


def collect_touched_paths(
    operations: list[AddOperation | DeleteOperation | UpdateOperation],
) -> list[str]:
    touched_ordered: dict[str, None] = {}
    for operation in operations:
        match operation:
            case AddOperation():
                touched_ordered[operation.target_path] = None
            case DeleteOperation():
                touched_ordered[operation.target_path] = None
            case UpdateOperation():
                touched_ordered[operation.source_path] = None
                touched_ordered[operation.dest_path] = None
    return list(touched_ordered.keys())


def build_file_snapshots(paths: list[str]) -> dict[str, FileSnapshot]:
    snapshots: dict[str, FileSnapshot] = {}
    for path in paths:
        if not os.path.exists(path):
            snapshots[path] = FileSnapshot(path=path, existed=False, content=None)
            continue
        if not os.path.isfile(path):
            raise ValidationError(f"Patch target path must be a file: {path}")
        try:
            with open_binary(path, mode="rb") as file_handle:
                content = file_handle.read()
        except OSError as os_exception:
            raise ValidationError(
                f"Failed to snapshot file {path}: {os_exception}",
            ) from os_exception
        snapshots[path] = FileSnapshot(path=path, existed=True, content=content)
    return snapshots


def restore_file_snapshots(
    snapshots: dict[str, FileSnapshot],
    *,
    rollback_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> list[str]:
    errors: list[str] = []
    ordered_snapshots = sorted(
        snapshots.values(),
        key=lambda snapshot: len(snapshot.path),
        reverse=True,
    )
    for snapshot in ordered_snapshots:
        try:
            if snapshot.existed:
                parent_dir = os.path.dirname(snapshot.path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                content = snapshot.content or b""
                with claim_reserved_write(rollback_reservation, size_bytes=len(content)):
                    with open_binary(snapshot.path, mode="wb") as file_handle:
                        file_handle.write(content)
                continue
            if os.path.isfile(snapshot.path):
                os.remove(snapshot.path)
        except OSError as os_exception:
            errors.append(f"{snapshot.path}: {os_exception}")
    return errors
