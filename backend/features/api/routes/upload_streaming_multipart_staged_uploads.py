"""SoAI - Shared staged multipart upload flows [backend/features/api/routes/upload_streaming_multipart_staged_uploads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.files.upload_batch_metadata import (
    parse_relative_paths_json,
    parse_relative_sizes_json,
)
from core.files.upload_size_validation import (
    ensure_staged_size_matches_declared,
    parse_size_bytes_field,
)
from features.api.routes.upload_streaming_multipart import (
    parse_and_stage_streaming_multipart,
)
from features.api.routes.upload_streaming_multipart_cleanup import (
    cleanup_staged_multipart_upload,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartResult,
    StreamingStagedPart,
)
from features.api.routes.upload_streaming_multipart_specs import (
    relative_paths_sizes_files_upload_spec,
    size_bytes_single_file_upload_spec,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol
    from core.logging.protocols import TraceLogger
    from features.api.routes.internal_protocols import (
        MultipartBytesReporter,
        MultipartFileStartReporter,
        StreamingMultipartWriteController,
    )

__all__ = (
    "BatchStagedUpload",
    "SingleStagedUpload",
    "stage_batch_relative_paths_sizes_upload",
    "stage_single_size_declared_upload",
)


@dataclass(frozen=True, slots=True)
class SingleStagedUpload:
    part: StreamingStagedPart
    declared_size: int
    content_type: str | None


@dataclass(frozen=True, slots=True)
class BatchStagedUpload:
    parsed: StreamingMultipartResult
    relative_paths: list[str]
    relative_sizes: list[int | None]


def _first_required_field(fields: dict[str, tuple[str, ...]], field_name: str) -> str:
    values = fields.get(field_name)
    if values is None or not values:
        raise ValidationError(f"Missing required field '{field_name}'.")
    return values[0]


def _cleanup_failed_staged_result(
    parsed: StreamingMultipartResult,
) -> None:
    result = cleanup_staged_multipart_upload(
        opened_writers=[],
        opened_paths=[part.temp_path for part in parsed.files],
    )
    if not result.succeeded:
        raise StateError(
            "Rejected multipart staging files could not be fully cleaned.",
            operation="api_routes.staged_upload.cleanup_rejected_result",
            details={"failed_path_count": len(result.failed_paths)},
        ) from result.first_failure


async def stage_single_size_declared_upload(
    request: Request,
    *,
    parser_semaphore: asyncio.Semaphore,
    temp_dir: str,
    max_upload_bytes: int | None,
    token: CancellationTokenProtocol,
    report_bytes: MultipartBytesReporter,
    logger: TraceLogger,
    write_controller: StreamingMultipartWriteController,
    report_file_start: MultipartFileStartReporter | None = None,
    report_stream_bytes: MultipartBytesReporter | None = None,
    on_declared_size: Callable[[int], None] | None = None,
) -> SingleStagedUpload:
    declared_size: int | None = None
    content_type: str | None = None

    def report_field(field_name: str, field_value: str) -> None:
        nonlocal content_type, declared_size
        if field_name == "size_bytes":
            declared_size = parse_size_bytes_field(
                field_value,
                max_upload_bytes=max_upload_bytes,
            )
            if on_declared_size is not None:
                on_declared_size(declared_size)
            return
        if field_name == "content_type":
            content_type = field_value

    parsed = await parse_and_stage_streaming_multipart(
        request,
        parser_semaphore=parser_semaphore,
        spec=size_bytes_single_file_upload_spec(temp_dir, max_upload_bytes=max_upload_bytes),
        token=token,
        report_bytes=report_bytes,
        report_field=report_field,
        report_file_start=report_file_start,
        report_stream_bytes=report_stream_bytes,
        write_controller=write_controller,
        logger=logger,
    )
    result_ready = False
    try:
        if len(parsed.files) != 1:
            raise ValidationError("Exactly one file must be provided.")
        part = parsed.files[0]
        if declared_size is None:
            raise ValidationError("size_bytes must be an integer.")
        ensure_staged_size_matches_declared(
            declared_size=declared_size,
            staged_size=part.size_bytes,
        )
        result = SingleStagedUpload(
            part=part,
            declared_size=declared_size,
            content_type=content_type,
        )
        result_ready = True
        return result
    finally:
        if not result_ready:
            _cleanup_failed_staged_result(parsed)


async def stage_batch_relative_paths_sizes_upload(
    request: Request,
    *,
    parser_semaphore: asyncio.Semaphore,
    temp_dir: str,
    max_upload_bytes: int | None,
    token: CancellationTokenProtocol,
    report_bytes: MultipartBytesReporter,
    logger: TraceLogger,
    write_controller: StreamingMultipartWriteController,
    report_file_start: MultipartFileStartReporter | None = None,
    report_stream_bytes: MultipartBytesReporter | None = None,
    allow_null_sizes: bool = False,
    allow_number_sizes: bool = False,
    on_declared_total: Callable[[int], None] | None = None,
) -> BatchStagedUpload:
    relative_paths: list[str] | None = None
    relative_sizes: list[int | None] | None = None

    def report_field(field_name: str, field_value: str) -> None:
        nonlocal relative_paths, relative_sizes
        if field_name == "relative_paths":
            relative_paths = parse_relative_paths_json(field_value)
            return
        if field_name != "relative_sizes":
            return
        parsed_sizes, total = parse_relative_sizes_json(
            field_value,
            max_file_bytes=max_upload_bytes,
            allow_null_items=allow_null_sizes,
            allow_number_items=allow_number_sizes,
        )
        relative_sizes = parsed_sizes
        if total > 0 and on_declared_total is not None and None not in parsed_sizes:
            on_declared_total(total)

    def resolved_relative_paths(parsed: StreamingMultipartResult) -> list[str]:
        if relative_paths is not None:
            return relative_paths
        return parse_relative_paths_json(_first_required_field(parsed.fields, "relative_paths"))

    def resolved_relative_sizes(parsed: StreamingMultipartResult) -> list[int | None]:
        if relative_sizes is not None:
            return relative_sizes
        parsed_sizes, _ = parse_relative_sizes_json(
            _first_required_field(parsed.fields, "relative_sizes"),
            max_file_bytes=max_upload_bytes,
            allow_null_items=allow_null_sizes,
            allow_number_items=allow_number_sizes,
        )
        return parsed_sizes

    parsed = await parse_and_stage_streaming_multipart(
        request,
        parser_semaphore=parser_semaphore,
        spec=relative_paths_sizes_files_upload_spec(temp_dir, max_upload_bytes=max_upload_bytes),
        token=token,
        report_bytes=report_bytes,
        report_field=report_field,
        report_file_start=report_file_start,
        report_stream_bytes=report_stream_bytes,
        write_controller=write_controller,
        logger=logger,
    )
    result_ready = False
    try:
        relative_paths = resolved_relative_paths(parsed)
        relative_sizes = resolved_relative_sizes(parsed)
        if len(relative_paths) != len(parsed.files) or len(relative_sizes) != len(parsed.files):
            raise ValidationError(
                "Number of relative_paths/relative_sizes must match number of files."
            )
        result = BatchStagedUpload(
            parsed=parsed,
            relative_paths=relative_paths,
            relative_sizes=relative_sizes,
        )
        result_ready = True
        return result
    finally:
        if not result_ready:
            _cleanup_failed_staged_result(parsed)
