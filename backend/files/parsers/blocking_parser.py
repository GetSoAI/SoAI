"""SoAI - Deadline-safe blocking file parser base [backend/files/parsers/blocking_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import abc
import asyncio

from core.errors.exceptions import StateError
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.types import ParsedDocument, ParseExecutionContext

__all__ = ("BlockingParser",)


class BlockingParser(abc.ABC):
    content_separator: str = "\n\n"

    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        raise_if_parse_cancelled(context)
        result = await asyncio.to_thread(self.parse_blocking, context.source_path)
        raise_if_parse_cancelled(context)
        return result

    @abc.abstractmethod
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        raise StateError(f"{self.__class__.__name__} must implement parse_blocking().")

    def _join_content(self, parts: list[str]) -> str:
        return self.content_separator.join(parts)
