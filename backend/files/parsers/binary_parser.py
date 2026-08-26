"""SoAI - Binary string extraction parser [backend/files/parsers/binary_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.types import ParsedDocument
from core.filesystem.open_files import open_binary
from files.parsers.blocking_parser import BlockingParser

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "BinaryParser",
    "BinaryParserConfig",
)


@dataclass(frozen=True, slots=True)
class BinaryParserConfig:
    min_length: int = 4
    max_file_size: int = 100 * MIB_BYTES


class BinaryParser(BlockingParser):
    content_separator: str = "\n"

    def __init__(self, config: BinaryParserConfig | None = None) -> None:
        self._config = config if config is not None else BinaryParserConfig()
        printable: set[int] = set(range(32, 127))
        printable.update((9, 10, 13))
        self._ascii_printable = frozenset(printable)

    def _append_if_valid(self, strings: list[str], current: list[str]) -> None:
        if len(current) < self._config.min_length:
            return
        candidate = "".join(current).strip()
        if len(candidate) >= self._config.min_length:
            strings.append(candidate)

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        file_size = os.path.getsize(file_path)
        if file_size > self._config.max_file_size:
            raise ValidationError(
                f"File too large for binary parsing ({file_size} bytes > {self._config.max_file_size} bytes)",
            )
        with open_binary(file_path, mode="rb") as file_handle:
            data = file_handle.read()
        ascii_strings = self._extract_ascii_strings(data)
        utf16_strings = self._extract_utf16_strings(data)
        all_strings = list(set(ascii_strings + utf16_strings))
        all_strings.sort(key=lambda sentence: (-len(sentence), sentence))
        metadata: JSONDict = {
            "file_size": file_size,
            "ascii_strings_count": len(ascii_strings),
            "utf16_strings_count": len(utf16_strings),
            "unique_strings_count": len(all_strings),
            "extraction_type": "binary_strings",
        }
        if not all_strings:
            if file_size == 0:
                return ParsedDocument(content="", metadata=metadata)
            content = self._join_content(
                [f"File size: {file_size} bytes", "No printable strings found"],
            )
            return ParsedDocument(content=content, metadata=metadata)
        return ParsedDocument(content=self._join_content(all_strings), metadata=metadata)

    def _extract_ascii_strings(self, data: bytes) -> list[str]:
        strings: list[str] = []
        current: list[str] = []
        for byte in data:
            if byte in self._ascii_printable:
                current.append(chr(byte))
                continue
            self._append_if_valid(strings, current)
            current = []
        self._append_if_valid(strings, current)
        return strings

    def _extract_utf16_strings(self, data: bytes) -> list[str]:
        strings: list[str] = []
        current: list[str] = []
        data_index = 0
        while data_index < len(data) - 1:
            low = data[data_index]
            high = data[data_index + 1]
            if high == 0 and low in self._ascii_printable:
                current.append(chr(low))
                data_index += 2
                continue
            self._append_if_valid(strings, current)
            current = []
            data_index += 1
        self._append_if_valid(strings, current)
        return strings
