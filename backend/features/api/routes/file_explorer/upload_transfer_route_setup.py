"""SoAI - Shared streaming upload route setup for File Explorer [backend/features/api/routes/file_explorer/upload_transfer_route_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.api.routes.file_explorer.upload_temp_directory import (
    resolve_upload_temp_directory,
)
from features.api.routes.file_explorer.upload_transfer_progress_pump import (
    UploadProgressPump,
)
from features.api.routes.file_explorer.upload_transfer_task_context import (
    UploadTaskContext,
    build_upload_task_metadata,
    create_upload_task_context,
)
from features.api.runtime.context import ApiContext
from features.file_explorer.path_resolution import canonicalize_virtual_path

__all__ = (
    "UploadTransferRouteSetup",
    "build_upload_progress_pump",
    "setup_file_explorer_streaming_upload_route",
)


@dataclass(frozen=True, slots=True)
class UploadTransferRouteSetup:
    base_path: str
    temp_dir: str
    task_context: UploadTaskContext


async def setup_file_explorer_streaming_upload_route(
    request: Request,
    *,
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    api_context: ApiContext,
    status_message: str,
    task_operation: str,
    file_count: int,
) -> UploadTransferRouteSetup:
    temp_dir = resolve_upload_temp_directory(request, api_context)
    base_path = canonicalize_virtual_path(root_scope, path)
    task_context = await create_upload_task_context(
        request,
        api_context=api_context,
        status_message=status_message,
        metadata=build_upload_task_metadata(
            operation=task_operation,
            destination_path=base_path,
            file_count=file_count,
            total_bytes=None,
        ),
    )
    return UploadTransferRouteSetup(
        base_path=base_path,
        temp_dir=temp_dir,
        task_context=task_context,
    )


def build_upload_progress_pump(
    *,
    setup: UploadTransferRouteSetup,
    api_context: ApiContext,
    label: str,
) -> UploadProgressPump:
    task_context = setup.task_context
    return UploadProgressPump(
        task_registry=task_context.registry,
        task_id=task_context.task_id,
        action="Uploading",
        label=label,
        total_bytes=None,
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=task_context.cancellation_id,
        owner="file_explorer_upload_progress",
    )
