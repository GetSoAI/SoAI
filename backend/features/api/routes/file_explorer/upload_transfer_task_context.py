"""SoAI - File explorer upload task creation context [backend/features/api/routes/file_explorer/upload_transfer_task_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from core.tasks.type_catalog import TASK_TYPE_FILE_EXPLORER_OP
from features.api.runtime.context import ApiContext
from features.api.runtime.task_creation_context import (
    create_working_task_from_request_context,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue

__all__ = (
    "UploadTaskContext",
    "build_upload_task_metadata",
    "create_upload_task_context",
)


@dataclass(frozen=True, slots=True)
class UploadTaskContext:
    registry: TaskRegistryProtocol
    task_id: str
    cancellation_id: str
    trace_id: str | None


def build_upload_task_metadata(
    *,
    operation: str,
    destination_path: str,
    file_count: int,
    total_bytes: int | None,
    extra: dict[str, JSONValue] | None = None,
) -> dict[str, JSONValue]:
    metadata: dict[str, JSONValue] = {
        "operation": operation,
        "path": destination_path,
        "file_count": file_count,
    }
    if total_bytes is not None:
        metadata["total_bytes"] = total_bytes
    if extra:
        metadata.update(extra)
    return metadata


async def create_upload_task_context(
    request: Request,
    *,
    api_context: ApiContext,
    status_message: str,
    metadata: dict[str, JSONValue],
) -> UploadTaskContext:
    created = await create_working_task_from_request_context(
        request=request,
        api_context=api_context,
        task_type=TASK_TYPE_FILE_EXPLORER_OP,
        status_message=status_message,
        metadata=metadata,
    )
    return UploadTaskContext(
        registry=created.registry,
        task_id=created.task.task_id,
        cancellation_id=created.task.cancellation_id,
        trace_id=created.trace_id,
    )
