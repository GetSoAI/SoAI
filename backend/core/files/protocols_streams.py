"""SoAI - Core file stream and parsing protocols [backend/core/files/protocols_streams.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.files.types import ParsedDocument, ParseExecutionContext

__all__ = (
    "FileParserProtocol",
    "SeekableStreamProtocol",
)


@runtime_checkable
class SeekableStreamProtocol(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...

    def seek(self, offset: int, _whence: int = 0, /) -> int: ...

    def tell(self) -> int: ...


class FileParserProtocol(Protocol):
    content_separator: str

    async def parse(self, context: ParseExecutionContext) -> ParsedDocument: ...
