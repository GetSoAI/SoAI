"""SoAI - Strict streaming multipart parsing and staging [backend/features/api/routes/upload_streaming_multipart.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from python_multipart.exceptions import FormParserError

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.upload_errors import MissingRequiredUploadMetadataError
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from features.api.middleware.request_body_guard import claim_streaming_multipart_body
from features.api.routes.internal_protocols import (
    MultipartBytesReporter,
    MultipartFieldReporter,
    MultipartFileStartReporter,
    StreamingMultipartReservationController,
    StreamingMultipartWriteController,
)
from features.api.routes.upload_streaming_multipart_ingestion import (
    drain_progress,
    finalize_parser_input,
    ingest_request_stream,
)
from features.api.routes.upload_streaming_multipart_models import (
    DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    StreamingMultipartResult,
    StreamingMultipartSpec,
    StreamingStagedPart,
)
from features.api.routes.upload_streaming_multipart_permit import (
    MultipartParserSemaphorePermit,
)
from features.api.routes.upload_streaming_multipart_primitives import (
    ensure_dir_exists,
    require_multipart_boundary,
    validate_spec,
)
from features.api.routes.upload_streaming_multipart_specs import (
    build_streaming_multipart_spec,
)
from features.api.routes.upload_streaming_multipart_threading import (
    cleanup_state,
    join_parser_thread_or_raise,
    start_parser_thread,
)
from features.api.routes.upload_streaming_multipart_worker_state import (
    StreamingMultipartWorkerState,
    build_worker_state,
)
from features.api.routes.upload_streaming_progress import (
    build_ignore_multipart_bytes_reporter,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "parse_and_stage_single_file_multipart",
    "parse_and_stage_streaming_multipart",
)

OPERATION = "api_routes.parse_streaming_multipart"
LOGGER_NAME = "SoAI.features.api.upload_streaming_multipart"


def _raise_worker_errors(
    state: StreamingMultipartWorkerState,
    callback_error: Exception | None,
) -> None:
    if callback_error is not None:
        raise callback_error
    state.raise_if_failed()


def _validate_parsed_parts(
    *,
    spec: StreamingMultipartSpec,
    fields: dict[str, list[str]],
    files: list[StreamingStagedPart],
) -> StreamingMultipartResult:
    missing_required = [name for name in spec.required_fields if name not in fields]
    if missing_required:
        raise MissingRequiredUploadMetadataError("Missing required metadata fields.")
    present_file_fields = frozenset(part.field_name for part in files)
    required_groups: dict[str, set[str]] = {}
    for name in spec.required_file_fields:
        base = name.removesuffix("[]")
        aliases = required_groups.get(base)
        if aliases is None:
            aliases = set[str]()
            required_groups[base] = aliases
        aliases.add(name)
    missing_groups = [
        base for base, aliases in required_groups.items() if not (present_file_fields & aliases)
    ]
    if missing_groups:
        raise ValidationError("Missing required file parts.")
    if not spec.allow_multiple_files and len(files) != 1:
        raise ValidationError("Exactly one file must be uploaded.")
    if spec.allow_multiple_files and not files:
        raise ValidationError("At least one file must be uploaded.")
    normalized_fields: dict[str, tuple[str, ...]] = {}
    for key, values in fields.items():
        if not key or not values:
            continue
        normalized_values = tuple(value for value in values if value)
        if normalized_values:
            normalized_fields[key] = normalized_values
    return StreamingMultipartResult(fields=normalized_fields, files=files)


async def parse_and_stage_single_file_multipart(
    request: Request,
    *,
    parser_semaphore: asyncio.Semaphore,
    required_fields: frozenset[str],
    allowed_fields: frozenset[str],
    temp_dir: str,
    max_file_bytes: int | None,
    token: CancellationTokenProtocol,
    reservation_controller: StreamingMultipartReservationController,
    max_field_bytes: int = DEFAULT_MULTIPART_METADATA_LIMIT_BYTES,
    logger: TraceLogger | None = None,
    logger_name: str | None = None,
) -> StreamingMultipartResult:
    spec = build_streaming_multipart_spec(
        required_fields=required_fields,
        allowed_fields=allowed_fields,
        required_file_fields=frozenset({"file"}),
        allowed_file_fields=frozenset({"file"}),
        allow_multiple_files=False,
        require_fields_before_files=False,
        temp_dir=temp_dir,
        max_file_bytes=max_file_bytes,
        max_total_file_bytes=max_file_bytes,
        max_field_bytes=max_field_bytes,
        max_total_field_bytes=max_field_bytes,
    )
    try:
        return await parse_and_stage_streaming_multipart(
            request,
            parser_semaphore=parser_semaphore,
            spec=spec,
            token=token,
            report_bytes=build_ignore_multipart_bytes_reporter(),
            report_field=None,
            write_controller=reservation_controller,
            logger=logger,
            logger_name=logger_name,
        )
    finally:
        reservation_controller.release_active_reservation()


async def parse_and_stage_streaming_multipart(
    request: Request,
    *,
    parser_semaphore: asyncio.Semaphore,
    spec: StreamingMultipartSpec,
    token: CancellationTokenProtocol,
    report_bytes: MultipartBytesReporter,
    report_field: MultipartFieldReporter | None,
    write_controller: StreamingMultipartWriteController,
    report_file_start: MultipartFileStartReporter | None = None,
    report_stream_bytes: MultipartBytesReporter | None = None,
    logger: TraceLogger | None = None,
    logger_name: str | None = None,
) -> StreamingMultipartResult:
    validate_spec(spec)
    ensure_dir_exists(spec.temp_dir)
    logger_instance = logger if logger is not None else get_logger(LOGGER_NAME)
    resolved_logger_name = logger_name if logger_name is not None else __name__
    await parser_semaphore.acquire()
    permit = MultipartParserSemaphorePermit(
        loop=asyncio.get_running_loop(),
        semaphore=parser_semaphore,
    )
    parser_thread = None
    try:
        content_type, boundary = require_multipart_boundary(request)
        state = build_worker_state()
        parser_thread = start_parser_thread(
            state=state,
            spec=spec,
            token=token,
            logger_name=resolved_logger_name,
            content_type=content_type,
            boundary=boundary,
            write_controller=write_controller,
            permit=permit,
        )
        should_cleanup = True
        try:
            claim_streaming_multipart_body(request.scope)
            callback_error = await ingest_request_stream(
                request,
                state=state,
                token=token,
                report_bytes=report_bytes,
                report_field=report_field,
                report_file_start=report_file_start,
                report_stream_bytes=report_stream_bytes,
                logger=logger_instance,
            )
            if callback_error is None:
                callback_error = drain_progress(
                    state=state,
                    report_bytes=report_bytes,
                    report_field=report_field,
                    report_file_start=report_file_start,
                    token=token,
                    logger=logger_instance,
                )
            await finalize_parser_input(
                state=state,
                token=token,
                callback_error=callback_error,
            )
            await join_parser_thread_or_raise(parser_thread, state=state, token=token)
            if callback_error is None:
                callback_error = drain_progress(
                    state=state,
                    report_bytes=report_bytes,
                    report_field=report_field,
                    report_file_start=report_file_start,
                    token=token,
                    logger=logger_instance,
                )
            _raise_worker_errors(state, callback_error)
            result = _validate_parsed_parts(
                spec=spec,
                fields=state.parts.fields,
                files=state.parts.files,
            )
            should_cleanup = False
            return result
        except FormParserError as exception:
            raise ValidationError("Invalid multipart payload.") from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="api_routes.parse_streaming_multipart",
            )
            log_exception(
                logger_instance,
                coerced,
                message="Unexpected error while parsing streaming multipart payload",
                operation=OPERATION,
            )
            raise StateError(
                "Failed to parse multipart payload due to an internal server error.",
                operation="api_routes.parse_streaming_multipart",
                cause=exception,
            ) from exception
        finally:
            await uncancel_then_cleanup(
                cleanup_state(
                    state=state,
                    parser_thread=parser_thread,
                    token=token,
                    logger=logger_instance,
                    should_cleanup=should_cleanup,
                ),
            )
    finally:
        if parser_thread is None:
            permit.release_without_worker()
