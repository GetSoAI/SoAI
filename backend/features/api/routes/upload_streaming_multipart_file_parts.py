"""SoAI - Streaming multipart temp-file writer [backend/features/api/routes/upload_streaming_multipart_file_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import time
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, StateError, ValidationError
from core.files.operations import secure_filename
from core.files.temp_files import create_secure_temp_file_descriptor
from core.files.upload_size_validation import UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE
from core.filesystem.file_sync import flush_and_fsync_file
from core.logging.protocols import TraceLogger
from features.api.routes.internal_protocols import (
    MultipartBytesReporter,
    MultipartFileStartReporter,
    MultipartPartWriterFactory,
    StreamingMultipartWriteController,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartSpec,
    StreamingStagedPart,
    decode_multipart_header_value,
)
from features.api.routes.upload_streaming_multipart_staging import (
    StreamingMultipartStagingSession,
)
from features.api.routes.upload_streaming_multipart_worker_state import StreamingMultipartParts

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "StreamingMultipartTempFileWriter",
    "build_streaming_multipart_file_factory",
)

OPERATION_OPEN_TEMP_FILE_CLEANUP = "upload_streaming_multipart_file_parts.open_temp_file.cleanup"
OPERATION_OPEN_TEMP_FILE_CLOSE_DESCRIPTOR = (
    "upload_streaming_multipart_file_parts.open_temp_file.close_descriptor"
)
OPEN_TEMP_FILE_CLOSE_FAILURE_MESSAGE = (
    "Failed to close temp file descriptor after open failure (non-critical)."
)


_WRITER_REPORT_THROTTLE_SECONDS: float = 0.1


class StreamingMultipartTempFileWriter:
    def __init__(
        self,
        file_name: bytes | None,
        field_name: bytes | None,
        content_type: str | None,
        *,
        spec: StreamingMultipartSpec,
        token: CancellationTokenProtocol,
        report_bytes: MultipartBytesReporter,
        report_file_start: MultipartFileStartReporter | None,
        parts: StreamingMultipartParts,
        write_controller: StreamingMultipartWriteController,
        staging_session: StreamingMultipartStagingSession,
        logger: TraceLogger,
    ) -> None:
        self._logger = logger
        self._spec = spec
        self._token = token
        self._report_bytes = report_bytes
        self._parts = parts
        self._write_controller = write_controller

        self._field_name = decode_multipart_header_value(field_name, field="file field name")
        self._original_filename = decode_multipart_header_value(file_name, field="filename")
        self._content_type = content_type

        if report_file_start is not None:
            report_file_start(self._original_filename)
        write_controller.file_started(self._original_filename)

        if self._field_name not in spec.allowed_file_fields:
            raise ValidationError(f"Unexpected file field '{self._field_name}'.")
        if not spec.allow_multiple_files and parts.file_count >= 1:
            raise ValidationError("Only one file may be uploaded.")
        if spec.require_fields_before_files:
            missing = [name for name in spec.required_fields if name not in parts.fields]
            if missing:
                raise ValidationError("Missing required metadata fields before file upload.")
        parts.file_count += 1

        suffix = f"_{secure_filename(self._original_filename)}"
        file_descriptor, self._temp_path = create_secure_temp_file_descriptor(
            directory=spec.temp_dir,
            prefix="tmpupload_multipart_",
            suffix=suffix,
        )
        try:
            self._handle: io.RawIOBase | None = io.FileIO(file_descriptor, mode="wb", closefd=True)
        except OSError:
            try:
                os.close(file_descriptor)
            except OSError as close_error:
                log_handled_exception(
                    self._logger,
                    close_error,
                    message=OPEN_TEMP_FILE_CLOSE_FAILURE_MESSAGE,
                    operation=OPERATION_OPEN_TEMP_FILE_CLOSE_DESCRIPTOR,
                    details={"file_descriptor": file_descriptor, "temp_path": self._temp_path},
                    level="debug",
                )
            try:
                os.remove(self._temp_path)
            except OSError as removal_error:
                log_handled_exception(
                    self._logger,
                    removal_error,
                    message="Failed to remove temp file after open failure (non-critical).",
                    operation=OPERATION_OPEN_TEMP_FILE_CLEANUP,
                    details={"temp_path": self._temp_path},
                    level="debug",
                )
            raise
        try:
            staging_session.register_path(self._temp_path)
            staging_session.register_writer(self)
        except StateError:
            self.close()
            staging_session.cleanup_path_immediately(self._temp_path)
            raise
        self._size_bytes = 0
        self._digest = hashlib.sha256()
        self._finalized = False
        self._last_report_time: float = 0.0

    def write(self, data: bytes) -> int:
        self._token.raise_if_cancelled()
        if not data:
            return 0
        data_length = len(data)
        next_size = self._size_bytes + data_length
        if self._spec.max_file_bytes is not None and next_size > self._spec.max_file_bytes:
            raise PayloadTooLargeError(UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE)
        next_total = self._parts.file_bytes_done + data_length
        if (
            self._spec.max_total_file_bytes is not None
            and next_total > self._spec.max_total_file_bytes
        ):
            raise PayloadTooLargeError(UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE)
        handle = self._handle
        if handle is None:
            raise StateError("Upload stream writer is closed.")
        write_scope = self._write_controller.open_write_scope(data_length)
        with write_scope:
            try:
                written_total = 0
                while written_total < data_length:
                    written = handle.write(data[written_total:])
                    if written <= 0:
                        raise StateError("Failed to write upload stream bytes.")
                    self._digest.update(data[written_total : written_total + written])
                    written_total += written
                    self._write_controller.record_written_bytes(written)
            except (OSError, ValueError) as exception:
                raise StateError("Failed to write upload stream bytes.") from exception
        self._size_bytes = next_size
        self._parts.file_bytes_done = next_total
        now = time.monotonic()
        if now - self._last_report_time >= _WRITER_REPORT_THROTTLE_SECONDS:
            self._report_bytes(next_total)
            self._last_report_time = now
        self._token.raise_if_cancelled()
        return written_total

    def finalize(self) -> None:
        self._token.raise_if_cancelled()
        if self._finalized:
            return
        handle = self._handle
        if handle is None:
            raise StateError("Upload stream writer is closed.")
        try:
            flush_and_fsync_file(handle)
        except (OSError, ValueError) as exception:
            raise StateError("Failed to finalize staged upload part.") from exception
        self._report_bytes(self._parts.file_bytes_done)
        staged = StreamingStagedPart(
            field_name=self._field_name,
            original_filename=self._original_filename,
            temp_path=self._temp_path,
            size_bytes=self._size_bytes,
            content_sha256=self._digest.hexdigest().lower(),
            content_type=self._content_type,
        )
        self._parts.files.append(staged)
        self._finalized = True

    def close(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            handle.close()
        finally:
            self._handle = None


def build_streaming_multipart_file_factory(
    *,
    spec: StreamingMultipartSpec,
    token: CancellationTokenProtocol,
    report_bytes: MultipartBytesReporter,
    report_file_start: MultipartFileStartReporter | None,
    parts: StreamingMultipartParts,
    write_controller: StreamingMultipartWriteController,
    staging_session: StreamingMultipartStagingSession,
    logger: TraceLogger,
) -> MultipartPartWriterFactory:
    def create_writer(
        file_name: bytes | None,
        field_name: bytes | None,
        content_type: str | None,
    ) -> StreamingMultipartTempFileWriter:
        return StreamingMultipartTempFileWriter(
            file_name,
            field_name,
            content_type,
            spec=spec,
            token=token,
            report_bytes=report_bytes,
            report_file_start=report_file_start,
            parts=parts,
            write_controller=write_controller,
            staging_session=staging_session,
            logger=logger,
        )

    return create_writer
