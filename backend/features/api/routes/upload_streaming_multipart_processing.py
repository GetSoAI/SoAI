"""SoAI - Streaming multipart parser thread and progress draining [backend/features/api/routes/upload_streaming_multipart_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import queue
from collections.abc import Callable
from typing import TYPE_CHECKING

from python_multipart.exceptions import FormParserError

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import PayloadTooLargeError, StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from features.api.routes.internal_protocols import (
    MultipartBytesReporter,
    MultipartFieldReporter,
    MultipartFileStartReporter,
    StreamingMultipartWriteController,
)
from features.api.routes.upload_streaming_multipart_file_parts import (
    build_streaming_multipart_file_factory,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartSpec,
    decode_multipart_header_value,
)
from features.api.routes.upload_streaming_multipart_parser import (
    BoundedMultipartField,
    StreamingMultipartParser,
)
from features.api.routes.upload_streaming_multipart_primitives import (
    BytesProgressEvent,
    FieldProgressEvent,
    FileStartProgressEvent,
    drain_and_signal_queue,
    drain_progress_events,
)
from features.api.routes.upload_streaming_multipart_worker_state import (
    StreamingMultipartParts,
    StreamingMultipartWorkerState,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "build_field_handler",
    "drain_progress_callbacks",
    "process_multipart_stream",
)

OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PROGRESS_CALLBACKS = (
    "api_routes.parse_streaming_multipart.progress_callbacks"
)


def drain_progress_callbacks(
    *,
    progress_queue: queue.SimpleQueue[
        BytesProgressEvent | FieldProgressEvent | FileStartProgressEvent
    ],
    report_bytes: MultipartBytesReporter,
    report_field: MultipartFieldReporter | None,
    report_file_start: MultipartFileStartReporter | None,
    token: CancellationTokenProtocol,
    logger: TraceLogger,
    chunk_queue: queue.Queue[bytes | None],
) -> Exception | None:

    def capture_callback_error(exception: Exception) -> Exception:
        token.cancel("Multipart progress callback failed.")
        drain_and_signal_queue(chunk_queue)
        return exception

    try:
        drain_progress_events(
            progress_queue,
            report_bytes=report_bytes,
            report_field=report_field,
            report_file_start=report_file_start,
        )
    except (ValidationError, PayloadTooLargeError, StateError, TaskCancelledError) as exception:
        return capture_callback_error(exception)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_routes.parse_streaming_multipart.progress_callbacks",
        )
        log_exception(
            logger,
            coerced,
            message="Unexpected error while replaying multipart parser progress callbacks",
            operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PROGRESS_CALLBACKS,
        )
        return capture_callback_error(coerced)
    return None


def build_field_handler(
    *,
    spec: StreamingMultipartSpec,
    parts: StreamingMultipartParts,
    progress_queue: queue.SimpleQueue[
        BytesProgressEvent | FieldProgressEvent | FileStartProgressEvent
    ],
) -> Callable[[BoundedMultipartField], None]:
    def on_field(field_obj: BoundedMultipartField) -> None:
        field_name_value = field_obj.field_name
        name = decode_multipart_header_value(field_name_value, field="field name")
        if name not in spec.allowed_fields:
            raise ValidationError(f"Unexpected field '{name}'.")
        if spec.require_fields_before_files and parts.file_count > 0:
            raise ValidationError("Metadata fields must be provided before files.")
        raw_value = field_obj.value
        if raw_value is None:
            raise ValidationError(f"Missing value for field '{name}'.")
        try:
            value = raw_value.decode("utf-8")
        except UnicodeDecodeError as exception:
            raise ValidationError(f"Invalid value encoding for field '{name}'.") from exception
        normalized = value.strip()
        if not normalized:
            raise ValidationError(f"Field '{name}' must not be empty.")
        existing = parts.fields.get(name)
        if existing is not None:
            if not name.endswith("[]"):
                raise ValidationError(f"Duplicate field '{name}'.")
            existing.append(normalized)
        else:
            parts.fields[name] = [normalized]
        progress_queue.put(FieldProgressEvent(name, normalized))

    return on_field


def process_multipart_stream(
    *,
    spec: StreamingMultipartSpec,
    token: CancellationTokenProtocol,
    logger: TraceLogger,
    content_type: str,
    boundary: bytes,
    state: StreamingMultipartWorkerState,
    write_controller: StreamingMultipartWriteController,
) -> None:
    def report_bytes_from_parser(bytes_done: int) -> None:
        state.progress_queue.put(BytesProgressEvent(max(0, int(bytes_done))))

    def report_file_start_from_parser(filename: str) -> None:
        state.progress_queue.put(FileStartProgressEvent(filename))

    on_field = build_field_handler(
        spec=spec,
        parts=state.parts,
        progress_queue=state.progress_queue,
    )
    file_factory = build_streaming_multipart_file_factory(
        spec=spec,
        token=token,
        report_bytes=report_bytes_from_parser,
        report_file_start=report_file_start_from_parser,
        parts=state.parts,
        write_controller=write_controller,
        staging_session=state.staging_session,
        logger=logger,
    )
    if content_type != "multipart/form-data":
        raise FormParserError(f"Unknown Content-Type: {content_type}")
    parser = StreamingMultipartParser(
        boundary=boundary,
        spec=spec,
        on_field=on_field,
        file_factory=file_factory,
    )
    while True:
        try:
            item = state.chunk_queue.get(timeout=0.5)
        except queue.Empty:
            token.raise_if_cancelled()
            continue
        if item is None:
            break
        token.raise_if_cancelled()
        parser.write(item)
        token.raise_if_cancelled()
    parser.finalize()
