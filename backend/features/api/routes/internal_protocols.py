"""SoAI - API routes internal protocols [backend/features/api/routes/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

__all__ = (
    "MultipartBytesReporter",
    "MultipartFieldReporter",
    "MultipartFileStartReporter",
    "MultipartPartWriter",
    "MultipartPartWriterFactory",
    "MultipartStagingWriter",
    "StreamingMultipartWriteController",
    "StreamingMultipartReservationController",
)


class MultipartBytesReporter(Protocol):

    def __call__(self, bytes_done: int, /) -> None: ...


class MultipartFieldReporter(Protocol):

    def __call__(self, field_name: str, field_value: str) -> None: ...


class MultipartFileStartReporter(Protocol):

    def __call__(self, filename: str) -> None: ...


class StreamingMultipartWriteController(Protocol):
    def parser_started(self) -> None: ...

    def parser_finished(self) -> None: ...

    def file_started(self, filename: str) -> None: ...

    def open_write_scope(self, bytes_to_write: int) -> AbstractContextManager[None]: ...

    def record_written_bytes(self, bytes_written: int) -> None: ...


class StreamingMultipartReservationController(StreamingMultipartWriteController, Protocol):
    def release_active_reservation(self) -> None: ...


class MultipartPartWriter(Protocol):

    def write(self, data: bytes) -> int: ...

    def finalize(self) -> None: ...

    def close(self) -> None: ...


class MultipartPartWriterFactory(Protocol):

    def __call__(
        self,
        file_name: bytes | None,
        field_name: bytes | None,
        content_type: str | None,
    ) -> MultipartPartWriter: ...


class MultipartStagingWriter(Protocol):

    def close(self) -> None: ...
