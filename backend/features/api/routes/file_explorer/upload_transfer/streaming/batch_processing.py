"""SoAI - Streaming batch upload processing [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.logging.trace import get_logger
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.file_explorer.path_resolution import (
    resolve_batch_upload_virtual_destination,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.files.protocols_explorer import (
        FileExplorerCoreProtocol,
        FileSystemRootScopeProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "StreamingBatchUploadOutcome",
    "process_streaming_batch_upload_parts",
)

LOGGER_NAME = "SoAI.features.api.batch_processing"
OPERATION_FILE_EXPLORER_UPLOAD_BATCH_MOVE = "file_explorer.upload.batch.move"
OPERATION_FILE_EXPLORER_UPLOAD_BATCH_NOTIFY = "file_explorer.upload.batch.notify"


@dataclass(frozen=True, slots=True)
class StreamingBatchUploadOutcome:
    succeeded: int
    failed: int
    actual_total_size: int
    results: list[JSONDict]
    moved_paths: list[str]
    created_virtual_paths: list[str]


async def process_streaming_batch_upload_parts(
    *,
    staged_parts: list[StreamingStagedPart],
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    parsed_paths: list[str],
    parsed_sizes: list[int],
    moved_paths: list[str],
    created_virtual_paths: list[str],
    file_explorer_core: FileExplorerCoreProtocol,
    token: CancellationTokenProtocol,
) -> StreamingBatchUploadOutcome:
    results: list[JSONDict] = []
    succeeded = 0
    reserved_virtual_destinations: set[str] = set()

    for staged_part, relative_path_value, declared_size in zip(
        staged_parts,
        parsed_paths,
        parsed_sizes,
        strict=True,
    ):
        token.raise_if_cancelled()
        if staged_part.size_bytes != declared_size:
            results.append(
                {"path": relative_path_value, "success": False, "error": "Declared size mismatch"},
            )
            continue
        try:
            virtual_destination = resolve_batch_upload_virtual_destination(
                root_scope,
                file_explorer_core,
                base_path=path,
                relative_path=relative_path_value,
            )
        except ValidationError as exception:
            results.append(
                {
                    "path": relative_path_value,
                    "success": False,
                    "error": project_public_exception(exception).message,
                },
            )
            continue
        if virtual_destination in reserved_virtual_destinations:
            results.append(
                {"path": virtual_destination, "success": False, "error": "Duplicate path"},
            )
            continue
        reserved_virtual_destinations.add(virtual_destination)
        real_destination = ""
        try:
            real_destination = await file_explorer_core.move_staged_upload(
                root_scope=root_scope,
                temp_path=staged_part.temp_path,
                expected_size=staged_part.size_bytes,
                virtual_destination=virtual_destination,
                token=token,
                create_missing_parents=True,
            )
        except MoveFileCommittedAfterCancellationError as exception:
            moved_paths.append(exception.destination_path)
            created_virtual_paths.append(virtual_destination)
            raise
        except ValidationError as exception:
            results.append(
                {
                    "path": virtual_destination,
                    "success": False,
                    "error": project_public_exception(exception).message,
                },
            )
            continue
        except RECOVERABLE_EXCEPTIONS as move_error:
            log_exception(
                get_logger(LOGGER_NAME),
                move_error,
                message=f"Failed to move staged file for {virtual_destination}",
                operation=OPERATION_FILE_EXPLORER_UPLOAD_BATCH_MOVE,
            )
            results.append(
                {
                    "path": virtual_destination,
                    "success": False,
                    "error": project_public_exception(move_error).message,
                },
            )
            continue
        moved_paths.append(real_destination)
        created_virtual_paths.append(virtual_destination)
        succeeded += 1
        results.append(
            {"path": virtual_destination, "success": True, "size": staged_part.size_bytes},
        )
        try:
            await file_explorer_core.notify_upload_complete(root_scope, virtual_destination)
        except RECOVERABLE_EXCEPTIONS as notify_error:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                notify_error,
                message="Failed to publish upload completion notification (non-critical).",
                operation=OPERATION_FILE_EXPLORER_UPLOAD_BATCH_NOTIFY,
                details={"path": virtual_destination},
                level="debug",
            )
    failed = len(staged_parts) - succeeded
    actual_total_size = 0
    for entry in results:
        if entry.get("success") is not True:
            continue
        size_value = entry.get("size")
        if isinstance(size_value, int):
            actual_total_size += int(size_value)
    return StreamingBatchUploadOutcome(
        succeeded=succeeded,
        failed=failed,
        actual_total_size=actual_total_size,
        results=results,
        moved_paths=list(moved_paths),
        created_virtual_paths=list(created_virtual_paths),
    )
