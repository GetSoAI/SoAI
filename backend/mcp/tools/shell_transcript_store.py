"""SoAI - MCP shell transcript storage and reading [backend/mcp/tools/shell_transcript_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import shutil
import threading
from bisect import bisect_right
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.filesystem.open_files import open_binary

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ShellTranscript",
    "build_empty_shell_output_payload",
)

_MAX_SHELL_TRANSCRIPT_BYTES: int = 64 * MIB_BYTES
_MAX_SHELL_OUTPUT_PAGE_BYTES: int = 512 * 1024


@dataclass(slots=True)
class ShellTranscript:
    path: str
    line_starts: list[int] = field(default_factory=lambda: [0])
    total_bytes: int = 0
    delivered_offset_bytes: int = 0
    truncated: bool = False
    lock: AbstractContextManager[bool] = field(default_factory=threading.RLock)

    def append(self, data: bytes) -> None:
        if not data:
            return
        with self.lock:
            if self.truncated:
                return
            remaining_bytes = _MAX_SHELL_TRANSCRIPT_BYTES - self.total_bytes
            if remaining_bytes <= 0:
                self.truncated = True
                return
            writable = data[:remaining_bytes]
            if len(writable) < len(data):
                self.truncated = True
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
            with open_binary(self.path, mode="ab") as file_handle:
                file_handle.write(writable)
            self._index_appended_bytes_locked(writable)

    def read_incremental(self, *, limit: int) -> JSONDict:
        with self.lock:
            result, next_output_offset_bytes = self._read_from_byte_offset_locked(
                self.delivered_offset_bytes,
                limit=limit,
            )
            self.delivered_offset_bytes = next_output_offset_bytes
            return result

    def read_lines(self, *, offset: int, limit: int, from_end: bool) -> JSONDict:
        with self.lock:
            total_lines = self._total_lines_locked()
            resolved_offset = max(1, total_lines - limit + 1) if from_end else offset
            start_index = max(0, min(resolved_offset - 1, total_lines))
            end_index = min(total_lines, start_index + limit)
            start_byte = self._line_start_byte_locked(start_index)
            end_byte = self._line_start_byte_locked(end_index)
            output = self._read_byte_range_locked(start_byte, end_byte)
            next_offset = end_index + 1 if end_index < total_lines else None
            return _build_page_payload(
                output=output,
                offset=resolved_offset,
                limit=limit,
                returned_lines=max(0, end_index - start_index),
                total_lines=total_lines,
                next_offset=next_offset,
                output_offset_bytes=start_byte,
                next_output_offset_bytes=end_byte,
                transcript_truncated=self.truncated,
            )

    def search(self, *, query: str, offset: int, limit: int, case_sensitive: bool) -> JSONDict:
        normalized_query = query if case_sensitive else query.lower()
        matches: list[JSONDict] = []
        next_offset: int | None = None
        with self.lock:
            total_lines = self._total_lines_locked()
            start_line = max(1, min(offset, total_lines + 1))
            if start_line <= total_lines:
                with open_binary(self.path, mode="rb") as file_handle:
                    for line_number in range(start_line, total_lines + 1):
                        line_text = self._read_line_from_handle_locked(
                            file_handle,
                            line_number,
                        )
                        haystack = line_text if case_sensitive else line_text.lower()
                        if normalized_query not in haystack:
                            continue
                        if len(matches) >= limit:
                            next_offset = line_number
                            break
                        matches.append({"line": line_number, "content": line_text})
            return {
                "query": query,
                "offset": start_line,
                "limit": limit,
                "total_lines": total_lines,
                "returned_matches": len(matches),
                "next_offset": next_offset,
                "has_more": next_offset is not None,
                "transcript_truncated": self.truncated,
                "matches": matches,
            }

    def snapshot_page(self, *, limit: int) -> JSONDict:
        with self.lock:
            result, _ = self._read_from_byte_offset_locked(0, limit=limit)
            return result

    def remove(self) -> None:
        with self.lock:
            try:
                shutil.rmtree(os.path.dirname(self.path))
            except OSError:
                return

    def _index_appended_bytes_locked(self, data: bytes) -> None:
        base_offset = self.total_bytes
        for byte_index, byte_value in enumerate(data):
            if byte_value == 10:
                self.line_starts.append(base_offset + byte_index + 1)
        self.total_bytes += len(data)
        self.delivered_offset_bytes = min(self.delivered_offset_bytes, self.total_bytes)

    def _read_from_byte_offset_locked(
        self, start_offset: int, *, limit: int
    ) -> tuple[JSONDict, int]:
        bounded_start = max(0, min(start_offset, self.total_bytes))
        end_offset, returned_lines = self._resolve_page_end_locked(bounded_start, limit=limit)
        output = self._read_byte_range_locked(bounded_start, end_offset)
        start_line = self._line_number_for_byte_offset_locked(bounded_start)
        next_line_offset = start_line + returned_lines if end_offset < self.total_bytes else None
        return (
            _build_page_payload(
                output=output,
                offset=start_line,
                limit=limit,
                returned_lines=returned_lines,
                total_lines=self._total_lines_locked(),
                next_offset=next_line_offset,
                output_offset_bytes=bounded_start,
                next_output_offset_bytes=end_offset,
                transcript_truncated=self.truncated,
            ),
            end_offset,
        )

    def _resolve_page_end_locked(self, start_offset: int, *, limit: int) -> tuple[int, int]:
        if start_offset >= self.total_bytes:
            return (self.total_bytes, 0)
        line_number = self._line_number_for_byte_offset_locked(start_offset)
        total_lines = self._total_lines_locked()
        target_end_line = min(total_lines, line_number + limit - 1)
        byte_end = (
            self.total_bytes
            if target_end_line >= total_lines
            else self._line_start_byte_locked(target_end_line)
        )
        if byte_end - start_offset <= _MAX_SHELL_OUTPUT_PAGE_BYTES:
            return (byte_end, max(0, target_end_line - line_number + 1))
        raw_page = self._read_byte_range_raw_locked(
            start_offset,
            start_offset + _MAX_SHELL_OUTPUT_PAGE_BYTES,
        )
        safe_end = _safe_utf8_prefix_end(raw_page, start_offset)
        returned_lines = max(1, raw_page[: max(0, safe_end - start_offset)].count(b"\n"))
        return (safe_end, returned_lines)

    def _read_line_from_handle_locked(
        self, file_handle: io.BufferedIOBase, line_number: int
    ) -> str:
        total_lines = self._total_lines_locked()
        if line_number < 1 or line_number > total_lines:
            return ""
        start_byte = self._line_start_byte_locked(line_number - 1)
        end_byte = (
            self.total_bytes
            if line_number == total_lines
            else self._line_start_byte_locked(line_number)
        )
        if end_byte <= start_byte:
            return ""
        file_handle.seek(start_byte)
        return (
            file_handle.read(end_byte - start_byte).decode("utf-8", errors="replace").rstrip("\n")
        )

    def _line_number_for_byte_offset_locked(self, byte_offset: int) -> int:
        return max(1, bisect_right(self.line_starts, byte_offset))

    def _line_start_byte_locked(self, line_index: int) -> int:
        if line_index < 0:
            return 0
        if line_index >= len(self.line_starts):
            return self.total_bytes
        return self.line_starts[line_index]

    def _total_lines_locked(self) -> int:
        if self.total_bytes <= 0:
            return 0
        if self.line_starts[-1] == self.total_bytes:
            return max(0, len(self.line_starts) - 1)
        return len(self.line_starts)

    def _read_byte_range_locked(self, start_byte: int, end_byte: int) -> str:
        return self._read_byte_range_raw_locked(start_byte, end_byte).decode(
            "utf-8",
            errors="replace",
        )

    def _read_byte_range_raw_locked(self, start_byte: int, end_byte: int) -> bytes:
        if end_byte <= start_byte or self.total_bytes <= 0:
            return b""
        with open_binary(self.path, mode="rb") as file_handle:
            file_handle.seek(start_byte)
            return file_handle.read(max(0, end_byte - start_byte))


def build_empty_shell_output_payload(*, limit: int) -> JSONDict:
    return _build_page_payload(
        output="",
        offset=1,
        limit=limit,
        returned_lines=0,
        total_lines=0,
        next_offset=None,
        output_offset_bytes=0,
        next_output_offset_bytes=0,
        transcript_truncated=False,
    )


def _build_page_payload(
    *,
    output: str,
    offset: int,
    limit: int,
    returned_lines: int,
    total_lines: int,
    next_offset: int | None,
    output_offset_bytes: int,
    next_output_offset_bytes: int,
    transcript_truncated: bool,
) -> JSONDict:
    return {
        "output": output,
        "offset": offset,
        "limit": limit,
        "returned_lines": returned_lines,
        "total_lines": total_lines,
        "next_offset": next_offset,
        "has_more": next_offset is not None,
        "output_offset_bytes": output_offset_bytes,
        "next_output_offset_bytes": next_output_offset_bytes,
        "transcript_truncated": transcript_truncated,
    }


def _safe_utf8_prefix_end(data: bytes, start_offset: int) -> int:
    end = len(data)
    while end > 0:
        try:
            data[:end].decode("utf-8")
            return start_offset + end
        except UnicodeDecodeError:
            end -= 1
    return start_offset + len(data)
