"""SoAI - Streaming multipart parser adapter [backend/features/api/routes/upload_streaming_multipart_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from python_multipart.decoders import Base64Decoder, QuotedPrintableDecoder
from python_multipart.exceptions import FormParserError
from python_multipart.multipart import (
    DEFAULT_MAX_HEADER_COUNT,
    DEFAULT_MAX_HEADER_SIZE,
    MultipartParser,
    parse_options_header,
)

from core.errors.exceptions import PayloadTooLargeError
from features.api.routes.internal_protocols import MultipartPartWriter
from features.api.routes.upload_streaming_multipart_models import StreamingMultipartSpec

if TYPE_CHECKING:
    from features.api.routes.internal_protocols import MultipartPartWriterFactory

__all__ = ("BoundedMultipartField", "StreamingMultipartParser")


class BoundedMultipartField:
    __slots__ = (
        "_field_name",
        "_maximum_bytes",
        "_parts",
        "_record_bytes",
        "_size_bytes",
    )

    def __init__(
        self,
        field_name: bytes | None,
        *,
        maximum_bytes: int,
        record_bytes: Callable[[int], None],
    ) -> None:
        self._field_name = field_name
        self._maximum_bytes = maximum_bytes
        self._parts: list[bytes] = []
        self._record_bytes = record_bytes
        self._size_bytes = 0

    def write(self, data: bytes) -> int:
        next_size = self._size_bytes + len(data)
        if next_size > self._maximum_bytes:
            raise PayloadTooLargeError(
                "Multipart metadata field exceeds the configured maximum size."
            )
        self._record_bytes(len(data))
        self._parts.append(data)
        self._size_bytes = next_size
        return len(data)

    def finalize(self) -> None:
        return

    def close(self) -> None:
        self._parts.clear()

    @property
    def field_name(self) -> bytes | None:
        return self._field_name

    @property
    def value(self) -> bytes:
        return b"".join(self._parts)


class StreamingMultipartParser:
    def __init__(
        self,
        *,
        boundary: bytes,
        spec: StreamingMultipartSpec,
        on_field: Callable[[BoundedMultipartField], None],
        file_factory: MultipartPartWriterFactory,
    ) -> None:
        self._spec = spec
        self._on_field = on_field
        self._file_factory = file_factory
        self._header_name_parts: list[bytes] = []
        self._header_value_parts: list[bytes] = []
        self._headers: dict[bytes, bytes] = {}
        self._field: BoundedMultipartField | None = None
        self._file: MultipartPartWriter | None = None
        self._writer: (
            BoundedMultipartField
            | MultipartPartWriter
            | Base64Decoder
            | QuotedPrintableDecoder
            | None
        ) = None
        self._is_file = False
        self._completed = False
        self._total_field_bytes = 0
        self._parser = MultipartParser(
            boundary,
            callbacks={
                "on_part_begin": self._on_part_begin,
                "on_part_data": self._on_part_data,
                "on_part_end": self._on_part_end,
                "on_header_field": self._on_header_field,
                "on_header_value": self._on_header_value,
                "on_header_end": self._on_header_end,
                "on_headers_finished": self._on_headers_finished,
                "on_end": self._on_end,
            },
            max_header_count=DEFAULT_MAX_HEADER_COUNT,
            max_header_size=DEFAULT_MAX_HEADER_SIZE,
        )

    def write(self, data: bytes) -> int:
        return self._parser.write(data)

    def finalize(self) -> None:
        self._parser.finalize()
        if not self._completed:
            raise FormParserError("Incomplete multipart payload.")
        self._clear_part_state()

    def _on_part_begin(self) -> None:
        if self._writer is not None:
            raise FormParserError("Multipart part started before previous part ended.")
        self._clear_part_state()

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        writer = self._writer
        if writer is None:
            raise FormParserError("Multipart part data started before headers finished.")
        writer.write(data[start:end])

    def _on_part_end(self) -> None:
        writer = self._writer
        if writer is None:
            raise FormParserError("Multipart part ended before headers finished.")
        writer.finalize()
        if self._is_file:
            file_writer = self._file
            if file_writer is None:
                raise FormParserError("Multipart file part missing writer.")
            file_writer.close()
            self._clear_part_state()
            return
        field = self._field
        if field is None:
            raise FormParserError("Multipart field part missing field.")
        try:
            self._on_field(field)
        finally:
            field.close()
            self._clear_part_state()

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_name_parts.append(data[start:end])

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_value_parts.append(data[start:end])

    def _on_header_end(self) -> None:
        header_name = b"".join(self._header_name_parts).lower()
        header_value = b"".join(self._header_value_parts)
        if not header_name:
            raise FormParserError("Multipart header name is empty.")
        self._headers[header_name] = header_value
        self._header_name_parts = []
        self._header_value_parts = []

    def _on_headers_finished(self) -> None:
        content_disposition = self._headers.get(b"content-disposition")
        _disposition, options = parse_options_header(content_disposition)
        field_name = options.get(b"name")
        if field_name is None:
            raise FormParserError("Field name not found in Content-Disposition.")
        filename = options.get(b"filename")
        content_type_header = self._headers.get(b"content-type")
        content_type = (
            content_type_header.decode("latin-1") if content_type_header is not None else None
        )
        if filename is None:
            self._field = BoundedMultipartField(
                field_name,
                maximum_bytes=self._spec.max_field_bytes,
                record_bytes=self._record_field_bytes,
            )
            self._writer = self._build_part_writer(self._field)
            return
        self._file = self._file_factory(filename, field_name, content_type)
        self._writer = self._build_part_writer(self._file)
        self._is_file = True

    def _build_part_writer(
        self,
        writer: BoundedMultipartField | MultipartPartWriter,
    ) -> BoundedMultipartField | MultipartPartWriter | Base64Decoder | QuotedPrintableDecoder:
        transfer_encoding = self._headers.get(b"content-transfer-encoding", b"7bit").lower()
        if transfer_encoding in (b"binary", b"8bit", b"7bit"):
            return writer
        if transfer_encoding == b"base64":
            return Base64Decoder(writer)
        if transfer_encoding == b"quoted-printable":
            return QuotedPrintableDecoder(writer)
        raise FormParserError("Unsupported multipart content-transfer-encoding.")

    def _record_field_bytes(self, bytes_written: int) -> None:
        next_total = self._total_field_bytes + bytes_written
        if next_total > self._spec.max_total_field_bytes:
            raise PayloadTooLargeError(
                "Multipart total metadata exceeds the configured maximum size."
            )
        self._total_field_bytes = next_total

    def _on_end(self) -> None:
        self._completed = True

    def _clear_part_state(self) -> None:
        self._headers = {}
        self._header_name_parts = []
        self._header_value_parts = []
        self._field = None
        self._file = None
        self._writer = None
        self._is_file = False
