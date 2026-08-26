"""SoAI - Shared document reading pipeline [backend/files/parsers/document_reading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.protocols import CancellationTokenProtocol
from core.di.validation import require_dependencies
from core.files.document_type_detection import (
    detect_mime_from_path,
    extract_extension,
)
from core.files.extraction_state import ExtractionState
from core.files.protocols import DocumentReaderProtocol, FileParserProtocol
from core.files.types import (
    DocumentReadResult,
    ParsedDocument,
    ParseExecutionContext,
)
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from files.parsers.document_ocr_types import DocumentOcrOutcome
from files.parsers.document_reading_pipeline_support import (
    normalize_metadata,
    remaining_timeout_sec,
    try_parse_document,
)
from files.parsers.document_reading_validation import normalize_document_read_inputs
from files.parsers.document_text_slicing import slice_document_text

if TYPE_CHECKING:
    from core.files.types import ParseProgressCallback
    from files.internal_protocols import DocumentOcrCoordinatorProtocol

__all__ = (
    "DocumentReadingPipeline",
    "DocumentReadingPipelineDependencies",
    "build_document_reading_pipeline",
)

LOGGER_NAME = "SoAI.files.parsers.document_reading"
OPERATION_DOCUMENT_READ_PARSE = "files.document_reading.parse"

_SLICE_SLACK_CHARS: int = 2000


@dataclass(frozen=True, slots=True)
class DocumentReadingPipelineDependencies:
    logger: StandardLogger
    ocr_coordinator: DocumentOcrCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DocumentReadingPipelineDependencies",
            logger=self.logger,
            ocr_coordinator=self.ocr_coordinator,
        )


class DocumentReadingPipeline(DocumentReaderProtocol):

    def __init__(self, deps: DocumentReadingPipelineDependencies) -> None:
        self._logger = deps.logger
        self._ocr_coordinator = deps.ocr_coordinator

    @override
    async def read_document_to_text(
        self,
        *,
        file_path: str,
        parser_registry: dict[str, FileParserProtocol],
        parse_timeout_sec: float,
        max_chars: int,
        offset_chars: int,
        display_name: str | None = None,
        cancellation_token: CancellationTokenProtocol | None = None,
        progress_callback: ParseProgressCallback | None = None,
    ) -> DocumentReadResult:
        normalized_inputs = normalize_document_read_inputs(
            file_path=file_path,
            parse_timeout_sec=parse_timeout_sec,
            max_chars=max_chars,
            offset_chars=offset_chars,
        )
        resolved_path = normalized_inputs.file_path
        timeout_sec = normalized_inputs.parse_timeout_sec
        max_chars_normalized = normalized_inputs.max_chars
        offset_chars_normalized = normalized_inputs.offset_chars
        start_time = time.monotonic()
        extraction_deadline = start_time + timeout_sec

        type_source = display_name or resolved_path
        extension = extract_extension(type_source)
        detected_mime = detect_mime_from_path(resolved_path)
        detected_type = detected_mime or (f"extension/{extension}" if extension else "unknown")

        warnings: list[str] = []
        parse_context = ParseExecutionContext(
            source_path=resolved_path,
            cancellation_token=cancellation_token,
            progress_callback=progress_callback,
            display_name=display_name,
            extraction_deadline=extraction_deadline,
        )
        parsed = await _try_parse(
            self._logger,
            extension=extension,
            detected_mime=detected_mime,
            parser_registry=parser_registry,
            timeout_sec=_remaining_timeout_sec(start_time=start_time, timeout_sec=timeout_sec),
            warnings=warnings,
            context=parse_context,
        )
        parser_used = parsed.parser_used
        content = parsed.document.content
        page_count = parsed.document.page_count
        metadata = parsed.document.metadata
        extraction_state = parsed.document.extraction_state
        warnings.extend(parsed.document.warnings)

        needed_chars = offset_chars_normalized + max_chars_normalized + _SLICE_SLACK_CHARS
        ocr_result = await self._ocr_coordinator.supplement(
            context=parse_context,
            tika_document=parsed.document,
            extension=extension,
            needed_chars=needed_chars,
        )
        if ocr_result.supplements:
            supplement_text = "\n\n".join(ocr_result.supplements)
            if not content.strip():
                parser_used = "tesseract_ocr"
            content = (
                f"{content}\n\n{supplement_text}".strip() if content.strip() else supplement_text
            )
            metadata = dict(metadata) if isinstance(metadata, dict) else {}
            metadata["ocr_engine"] = "tesseract"
            warnings.append("Tesseract OCR supplemented raster-only document content.")
            if extraction_state in {ExtractionState.FAILED, ExtractionState.TIMED_OUT}:
                extraction_state = ExtractionState.DEGRADED
        if page_count is None and ocr_result.page_count is not None:
            page_count = ocr_result.page_count
        if ocr_result.outcome is DocumentOcrOutcome.TIMED_OUT:
            warnings.append("Document OCR timed out.")
            extraction_state = (
                ExtractionState.DEGRADED if content.strip() else ExtractionState.TIMED_OUT
            )
        elif ocr_result.outcome is DocumentOcrOutcome.UNSUPPORTED:
            warnings.append("Document OCR unsupported.")
            if extraction_state is not ExtractionState.UNSUPPORTED:
                extraction_state = (
                    ExtractionState.DEGRADED if content.strip() else ExtractionState.FAILED
                )
        elif ocr_result.outcome in {
            DocumentOcrOutcome.UNAVAILABLE,
            DocumentOcrOutcome.FAILED,
        }:
            warnings.append(f"Document OCR {ocr_result.outcome.value}.")
            extraction_state = (
                ExtractionState.DEGRADED if content.strip() else ExtractionState.FAILED
            )
        elif not ocr_result.complete:
            warnings.append("Document OCR stopped after satisfying the requested text slice.")
            extraction_state = ExtractionState.DEGRADED

        metadata_result = normalize_metadata(metadata)
        warnings.extend(metadata_result.warnings)
        return slice_document_text(
            content=content,
            parser_used=parser_used or "unknown",
            detected_type=detected_type,
            page_count=page_count,
            metadata=metadata_result.metadata,
            warnings=tuple(warnings),
            max_chars=max_chars_normalized,
            offset_chars=offset_chars_normalized,
            extraction_state=extraction_state,
        )


def build_document_reading_pipeline(
    ocr_coordinator: DocumentOcrCoordinatorProtocol,
) -> DocumentReadingPipeline:
    logger = get_logger(LOGGER_NAME)
    return DocumentReadingPipeline(
        DocumentReadingPipelineDependencies(
            logger=logger,
            ocr_coordinator=ocr_coordinator,
        ),
    )


@dataclass(frozen=True, slots=True)
class _ParseAttempt:
    document: ParsedDocument
    parser_used: str


async def _try_parse(
    logger: StandardLogger,
    *,
    extension: str,
    detected_mime: str,
    parser_registry: dict[str, FileParserProtocol],
    timeout_sec: float,
    warnings: list[str],
    context: ParseExecutionContext,
) -> _ParseAttempt:
    parsed = await try_parse_document(
        logger,
        extension=extension,
        detected_mime=detected_mime,
        parser_registry=parser_registry,
        timeout_sec=timeout_sec,
        warnings=warnings,
        operation=OPERATION_DOCUMENT_READ_PARSE,
        context=context,
    )
    return _ParseAttempt(document=parsed.document, parser_used=parsed.parser_used)


def _remaining_timeout_sec(*, start_time: float, timeout_sec: float) -> float:
    return remaining_timeout_sec(start_time=start_time, timeout_sec=timeout_sec)
