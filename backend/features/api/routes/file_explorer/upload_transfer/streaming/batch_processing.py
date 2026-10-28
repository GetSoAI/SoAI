"""SoAI - Streaming batch upload processing [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload, project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import (
    FileCleanupIncompleteError,
    FileCommitReceipt,
    FilePublicationUncertainError,
)
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.filesystem.operation_errors import build_filesystem_operation_error
from core.logging.trace import get_logger
from features.api.routes.file_explorer.upload_transfer.streaming.exception_handling import (
    enrich_upload_publication_error,
)
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
    receipts: list[FileCommitReceipt]

    def to_dict(self, *, path: str, total_files: int) -> JSONDict:
        return {
            "path": path,
            "total": total_files,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "total_size": self.actual_total_size,
            "results": self.results,
        }

    @staticmethod
    def failure_result(*, path: str, exception: BaseException) -> JSONDict:
        public_error = project_public_exception(exception)
        return {
            "path": path,
            "success": False,
            "error": public_error.message,
            "code": public_error.code,
        }

    def uncertainty_details(
        self, *, path: str, requested_total: int, unattempted_paths: list[str]
    ) -> JSONDict:
        return {
            **self.to_dict(path=path, total_files=len(self.results) + 1),
            "failed": len(self.results) + 1 - self.succeeded,
            "requested_total": requested_total,
            "unattempted_paths": unattempted_paths,
        }


async def process_streaming_batch_upload_parts(
    *,
    staged_parts: list[StreamingStagedPart],
    file_content_pool: BoundedBlockingPool,
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    parsed_paths: list[str],
    parsed_sizes: list[int],
    receipts: list[FileCommitReceipt],
    file_explorer_core: FileExplorerCoreProtocol,
    token: CancellationTokenProtocol,
) -> StreamingBatchUploadOutcome:
    results: list[JSONDict] = []
    succeeded = 0
    actual_total_size = 0
    reserved_virtual_destinations: set[str] = set()
    attempted_count = 0
    current_path = path

    try:
        for part_index, (staged_part, relative_path_value, declared_size) in enumerate(
            zip(staged_parts, parsed_paths, parsed_sizes, strict=True)
        ):
            token.raise_if_cancelled()
            attempted_count = part_index + 1
            current_path = relative_path_value
            committed_cancellation: MoveFileCommittedAfterCancellationError | None = None
            if staged_part.size_bytes != declared_size:
                results.append(
                    {
                        "path": relative_path_value,
                        "success": False,
                        "error": "Declared size mismatch",
                    },
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
                    StreamingBatchUploadOutcome.failure_result(
                        path=relative_path_value,
                        exception=exception,
                    ),
                )
                continue
            if virtual_destination in reserved_virtual_destinations:
                results.append(
                    {"path": virtual_destination, "success": False, "error": "Duplicate path"},
                )
                continue
            reserved_virtual_destinations.add(virtual_destination)
            current_path = virtual_destination
            try:
                receipt = await file_explorer_core.move_staged_upload(
                    root_scope=root_scope,
                    temp_path=staged_part.temp_path,
                    expected_size=staged_part.size_bytes,
                    expected_sha256=staged_part.content_sha256,
                    file_content_pool=file_content_pool,
                    virtual_destination=virtual_destination,
                    token=token,
                    create_missing_parents=True,
                )
            except MoveFileCommittedAfterCancellationError as exception:
                if exception.receipt is None:
                    raise FilePublicationUncertainError(
                        "The upload worker supplied no verified publication receipt."
                    ) from exception
                receipt = exception.receipt
                committed_cancellation = exception
            except ValidationError as exception:
                results.append(
                    StreamingBatchUploadOutcome.failure_result(
                        path=virtual_destination,
                        exception=exception,
                    ),
                )
                continue
            except (TaskCancelledError, FilePublicationUncertainError, FileCleanupIncompleteError):
                raise
            except HANDLED_RUNTIME_EXCEPTIONS as move_error:
                failure = (
                    build_filesystem_operation_error(move_error)
                    if isinstance(move_error, OSError)
                    else move_error
                )
                log_exception(
                    get_logger(LOGGER_NAME),
                    move_error,
                    message=f"Failed to move staged file for {virtual_destination}",
                    operation=OPERATION_FILE_EXPLORER_UPLOAD_BATCH_MOVE,
                )
                results.append(
                    StreamingBatchUploadOutcome.failure_result(
                        path=virtual_destination,
                        exception=failure,
                    ),
                )
                continue
            receipts.append(receipt)
            succeeded += 1
            actual_total_size += staged_part.size_bytes
            results.append(
                {"path": virtual_destination, "success": True, "size": staged_part.size_bytes},
            )
            if committed_cancellation is not None:
                raise committed_cancellation
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
        token.raise_if_cancelled()
    except (FilePublicationUncertainError, FileCleanupIncompleteError) as exception:
        partial = StreamingBatchUploadOutcome(
            succeeded=succeeded,
            failed=len(results) + 1 - succeeded,
            actual_total_size=actual_total_size,
            results=list(results),
            receipts=list(receipts),
        )
        enrich_upload_publication_error(
            exception,
            root_scope=root_scope,
            destination=current_path,
            receipts=receipts,
            details=partial.uncertainty_details(
                path=path,
                requested_total=len(staged_parts),
                unattempted_paths=[
                    resolve_batch_upload_virtual_destination(
                        root_scope, file_explorer_core, base_path=path, relative_path=remaining
                    )
                    for remaining in parsed_paths[attempted_count:]
                ],
            ),
        )
        raise
    except (TaskCancelledError, asyncio.CancelledError) as exception:
        if len(results) < attempted_count:
            results.append(
                {
                    "path": current_path,
                    "success": False,
                    "error": "Upload cancelled.",
                    "code": "cancelled",
                }
            )
        partial = StreamingBatchUploadOutcome(
            succeeded=succeeded,
            failed=len(results) - succeeded,
            actual_total_size=actual_total_size,
            results=results,
            receipts=list(receipts),
        )
        cancellation = (
            exception
            if isinstance(exception, TaskCancelledError)
            else TaskCancelledError(token.cancellation_id)
        )
        apply_public_error_payload(
            cancellation,
            ErrorPublicPayload(
                code="cancelled",
                message="File explorer batch upload was cancelled.",
                http_status=499,
                details={
                    "requested_total": len(staged_parts),
                    "unattempted_paths": [
                        resolve_batch_upload_virtual_destination(
                            root_scope, file_explorer_core, base_path=path, relative_path=remaining
                        )
                        for remaining in parsed_paths[attempted_count:]
                    ],
                    "pre_cleanup_result": partial.to_dict(path=path, total_files=len(results)),
                },
            ),
        )
        if isinstance(exception, asyncio.CancelledError):
            cancellation.cause = exception.__cause__ or exception.__context__
            cancellation.__cause__ = cancellation.cause
            exception.__cause__ = cancellation
        raise
    failed = len(staged_parts) - succeeded
    return StreamingBatchUploadOutcome(
        succeeded=succeeded,
        failed=failed,
        actual_total_size=actual_total_size,
        results=results,
        receipts=list(receipts),
    )
