"""SoAI - File explorer batch operations service [backend/features/file_explorer/batch_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.files.explorer_models import (
    BatchMetadataItemResult,
    BatchMetadataResult,
    BatchOperationItemResult,
    BatchOperationResult,
)
from features.file_explorer.dependencies import FileExplorerBatchServiceDependencies
from features.file_explorer.path_resolution import canonicalize_virtual_path

if TYPE_CHECKING:
    from core.files.protocols_explorer import FileSystemRootScopeProtocol

__all__ = ("FileExplorerBatchService",)


class FileExplorerBatchService:
    __slots__ = ("_core",)

    def __init__(self, deps: FileExplorerBatchServiceDependencies) -> None:
        self._core = deps.core

    async def delete_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: list[str],
    ) -> BatchOperationResult:
        results: list[BatchOperationItemResult] = []
        for raw_path in virtual_paths:
            try:
                vpath = canonicalize_virtual_path(root_scope, raw_path)
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchOperationItemResult(path=raw_path, success=False, error_message=str(ex)),
                )
                continue
            try:
                await self._core.delete_entry(root_scope, vpath)
                results.append(BatchOperationItemResult(path=vpath, success=True))
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchOperationItemResult(path=vpath, success=False, error_message=str(ex)),
                )
        succeeded = sum(1 for result_item in results if result_item.success)
        return BatchOperationResult(
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )

    async def move_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> BatchOperationResult:
        return await self._run_transfer_batch(
            root_scope,
            source_paths,
            destination_dir,
            operation="move",
            destination_missing_operation="file_explorer.move_entries_batch",
            overwrite=overwrite,
        )

    async def copy_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> BatchOperationResult:
        return await self._run_transfer_batch(
            root_scope,
            source_paths,
            destination_dir,
            operation="copy",
            destination_missing_operation="file_explorer.copy_entries_batch",
            overwrite=overwrite,
        )

    async def _run_transfer_batch(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_paths: list[str],
        destination_dir: str,
        *,
        operation: str,
        destination_missing_operation: str,
        overwrite: bool,
    ) -> BatchOperationResult:
        destination_dir = canonicalize_virtual_path(root_scope, destination_dir)
        dest_real = root_scope.resolve(destination_dir)
        if not os.path.isdir(dest_real):
            raise NotFoundError(
                "Destination directory not found.",
                operation=destination_missing_operation,
            )
        if operation not in {"copy", "move"}:
            raise ValidationError("Unsupported transfer batch operation.")
        results: list[BatchOperationItemResult] = []
        reserved_destinations: set[str] = set()
        for raw_src_path in source_paths:
            try:
                src_path = canonicalize_virtual_path(root_scope, raw_src_path)
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchOperationItemResult(
                        path=raw_src_path,
                        success=False,
                        error_message=str(ex),
                    ),
                )
                continue
            try:
                normalized_src = src_path.rstrip("/") or "/"
                name = os.path.basename(normalized_src)
                if not name:
                    raise ValidationError(
                        "Cannot perform batch operation on root directory.",
                    )
                dest_path = f"{destination_dir.rstrip('/')}/{name}"
                if dest_path in reserved_destinations:
                    results.append(
                        BatchOperationItemResult(
                            path=src_path,
                            success=False,
                            error_message="Duplicate destination path in batch operation.",
                        ),
                    )
                    continue
                reserved_destinations.add(dest_path)
                if operation == "move":
                    await self._core.move_entry(
                        root_scope,
                        src_path,
                        dest_path,
                        overwrite=overwrite,
                    )
                else:
                    await self._core.copy_entry(
                        root_scope,
                        src_path,
                        dest_path,
                        overwrite=overwrite,
                    )
                results.append(BatchOperationItemResult(path=src_path, success=True))
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchOperationItemResult(path=src_path, success=False, error_message=str(ex)),
                )
        succeeded = sum(1 for result_item in results if result_item.success)
        return BatchOperationResult(
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )

    async def get_metadata(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: list[str],
    ) -> BatchMetadataResult:
        results: list[BatchMetadataItemResult] = []
        for raw_path in virtual_paths:
            try:
                vpath = canonicalize_virtual_path(root_scope, raw_path)
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchMetadataItemResult(path=raw_path, success=False, error_message=str(ex)),
                )
                continue
            try:
                metadata = await self._core.get_metadata(root_scope, vpath, include_hash=False)
                results.append(BatchMetadataItemResult(path=vpath, success=True, metadata=metadata))
            except (NotFoundError, SecurityError, ValidationError) as ex:
                results.append(
                    BatchMetadataItemResult(path=vpath, success=False, error_message=str(ex)),
                )
        succeeded = sum(1 for result_item in results if result_item.success)
        return BatchMetadataResult(
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )
