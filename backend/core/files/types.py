"""SoAI - Core file parsing types [backend/core/files/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.files.extraction_state import ExtractionState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict

    type ParseProgressCallback = Callable[[float, str], Awaitable[None]]

__all__ = (
    "DocumentReadResult",
    "ParseExecutionContext",
    "ParsedDocument",
)


@dataclass(frozen=True, slots=True)
class ParseExecutionContext:
    source_path: str
    cancellation_token: CancellationTokenProtocol | None
    progress_callback: ParseProgressCallback | None
    display_name: str | None
    extraction_deadline: float

    def remaining_seconds(self) -> float:
        return max(0.0, self.extraction_deadline - time.monotonic())

    def with_source(self, source_path: str, display_name: str | None) -> ParseExecutionContext:
        return ParseExecutionContext(
            source_path=source_path,
            cancellation_token=self.cancellation_token,
            progress_callback=self.progress_callback,
            display_name=display_name,
            extraction_deadline=self.extraction_deadline,
        )


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    content: str
    page_count: int | None = None
    metadata: JSONDict | None = None
    extraction_state: ExtractionState = ExtractionState.COMPLETE
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentReadResult:
    content: str
    parser_used: str
    detected_type: str
    page_count: int | None
    metadata: JSONDict | None
    truncated: bool
    warnings: tuple[str, ...]
    offset_chars: int
    next_offset_chars: int | None
    total_chars: int | None
    extraction_state: ExtractionState = ExtractionState.COMPLETE
