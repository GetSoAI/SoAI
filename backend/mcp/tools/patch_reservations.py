"""SoAI - MCP apply_patch disk reservation planning [backend/mcp/tools/patch_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import InsufficientDiskSpaceError
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from mcp.tools.error import MCPToolError
from mcp.tools.patch_types import (
    AddOperation,
    DeleteOperation,
    FileSnapshot,
    UpdateOperation,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

__all__ = (
    "encoded_text_size_bytes",
    "reserve_patch_operation_writes",
    "reserve_patch_rollback_snapshots",
)


def encoded_text_size_bytes(content: str) -> int:
    return len(content.encode("utf-8", errors="replace"))


def reserve_patch_operation_writes(
    storage_manager: StorageManagerProtocol,
    operations: list[AddOperation | DeleteOperation | UpdateOperation],
) -> DiskSpaceReservationLeaseProtocol | None:
    requests: list[DiskSpaceReservationRequest] = []
    for operation in operations:
        match operation:
            case AddOperation():
                required_bytes = encoded_text_size_bytes(operation.content_text)
                path = operation.target_path
                operation_name = "mcp.tools.apply_patch.add_file"
                rel_path = operation.rel_path
            case UpdateOperation():
                required_bytes = encoded_text_size_bytes(operation.updated_text)
                path = operation.dest_path
                operation_name = "mcp.tools.apply_patch.update_file"
                rel_path = operation.diff_path
            case DeleteOperation():
                continue
            case _:
                raise MCPToolError(-32603, "Unsupported apply_patch operation.")
        if required_bytes == 0:
            continue
        requests.append(
            DiskSpaceReservationRequest(
                path=path,
                required_bytes=required_bytes,
                operation=operation_name,
                details={
                    "path": rel_path,
                    "required_bytes": required_bytes,
                },
            ),
        )
    if not requests:
        return None
    try:
        return storage_manager.reserve_many_disk_spaces(requests=requests)
    except InsufficientDiskSpaceError as exception:
        raise MCPToolError(-32603, str(exception)) from exception


def reserve_patch_rollback_snapshots(
    storage_manager: StorageManagerProtocol,
    snapshots: dict[str, FileSnapshot],
) -> DiskSpaceReservationLeaseProtocol | None:
    requests: list[DiskSpaceReservationRequest] = []
    ordered_snapshots = sorted(
        snapshots.values(),
        key=lambda snapshot: len(snapshot.path),
        reverse=True,
    )
    for snapshot in ordered_snapshots:
        if not snapshot.existed:
            continue
        content = snapshot.content or b""
        required_bytes = len(content)
        if required_bytes == 0:
            continue
        requests.append(
            DiskSpaceReservationRequest(
                path=snapshot.path,
                required_bytes=required_bytes,
                operation="mcp.tools.apply_patch.rollback_restore",
                details={
                    "path": snapshot.path,
                    "required_bytes": required_bytes,
                },
            ),
        )
    if not requests:
        return None
    try:
        return storage_manager.reserve_many_disk_spaces(requests=requests)
    except InsufficientDiskSpaceError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
