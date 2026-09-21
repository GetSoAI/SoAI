"""SoAI - Central document OCR coordination [backend/files/parsers/document_ocr.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy
from PIL import Image

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.types import ParsedDocument, ParseExecutionContext
from core.media.ocr_engine import ocr_tesseract_image_to_text
from files.parsers.document_ocr_rasters import (
    extract_ordered_document_rasters,
    supports_document_raster_extraction,
)
from files.parsers.document_ocr_types import (
    DocumentOcrOutcome,
    DocumentOcrResult,
    RasterCandidate,
)

if TYPE_CHECKING:
    from core.logging.protocols import StandardLogger
    from core.media.image_preprocessing import ImagePreprocessor

__all__ = ("DocumentOcrCoordinator", "DocumentOcrCoordinatorDependencies")

OPERATION_RASTER_EXTRACTION = "files.parsers.document_ocr.raster_extraction"
OPERATION_TESSERACT = "files.parsers.document_ocr.tesseract"


@dataclass(frozen=True, slots=True)
class DocumentOcrCoordinatorDependencies:
    preprocessor: ImagePreprocessor | None
    logger: StandardLogger

    def __post_init__(self) -> None:
        require_dependencies(owner="DocumentOcrCoordinatorDependencies", logger=self.logger)


class DocumentOcrCoordinator:
    def __init__(self, deps: DocumentOcrCoordinatorDependencies) -> None:
        self._preprocessor = deps.preprocessor
        self._logger = deps.logger

    async def supplement(
        self,
        *,
        context: ParseExecutionContext,
        tika_document: ParsedDocument,
        extension: str,
        needed_chars: int,
    ) -> DocumentOcrResult:
        if not supports_document_raster_extraction(extension):
            outcome = (
                DocumentOcrOutcome.SUCCEEDED
                if tika_document.content.strip()
                else DocumentOcrOutcome.UNSUPPORTED
            )
            return DocumentOcrResult(outcome=outcome)
        raise_if_parse_cancelled(context)
        try:
            async with scoped_temp_directory(
                directory=None,
                prefix="soai-document-ocr-",
                operation_label="document-ocr",
            ) as scratch_directory:
                candidates, page_count = await run_joined_thread_call(
                    extract_ordered_document_rasters,
                    context.source_path,
                    extension,
                    scratch_directory,
                    context.extraction_deadline,
                    (
                        context.cancellation_token.thread_event
                        if context.cancellation_token is not None
                        else None
                    ),
                    task_name="document-ocr-raster-extraction",
                )
                if not candidates:
                    outcome = (
                        DocumentOcrOutcome.SUCCEEDED
                        if tika_document.content.strip()
                        else DocumentOcrOutcome.UNSUPPORTED
                    )
                    return DocumentOcrResult(outcome=outcome, page_count=page_count)
                return await self._ocr_candidates(
                    context=context,
                    tika_content=tika_document.content,
                    candidates=candidates,
                    page_count=page_count,
                    needed_chars=needed_chars,
                )
        except TimeoutError:
            return DocumentOcrResult(outcome=DocumentOcrOutcome.TIMED_OUT, complete=False)
        except FileNotFoundError:
            return DocumentOcrResult(outcome=DocumentOcrOutcome.UNAVAILABLE, complete=False)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Document OCR raster extraction failed.",
                operation=OPERATION_RASTER_EXTRACTION,
                level="warning",
            )
            return DocumentOcrResult(outcome=DocumentOcrOutcome.FAILED, complete=False)

    async def _ocr_candidates(
        self,
        *,
        context: ParseExecutionContext,
        tika_content: str,
        candidates: tuple[RasterCandidate, ...],
        page_count: int | None,
        needed_chars: int,
    ) -> DocumentOcrResult:
        normalized_tika_content = _normalize_text(tika_content)
        normalized_seen: set[str] = {normalized_tika_content} if normalized_tika_content else set()
        supplements: list[str] = []
        total_chars = 0
        for candidate in candidates:
            raise_if_parse_cancelled(context)
            remaining_seconds = context.remaining_seconds()
            if remaining_seconds <= 0:
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.TIMED_OUT,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
            try:
                text = await run_joined_thread_call(
                    _ocr_raster_candidate,
                    candidate.path,
                    self._preprocessor,
                    remaining_seconds,
                    context.ocr_language,
                    task_name="document-ocr-tesseract",
                )
            except FileNotFoundError:
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.UNAVAILABLE,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
            except StateError:
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.UNAVAILABLE,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
            except TimeoutError:
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.TIMED_OUT,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Document OCR execution failed.",
                    operation=OPERATION_TESSERACT,
                    level="warning",
                )
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.FAILED,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
            text = _retain_novel_ocr_lines(
                text,
                normalized_tika_content=normalized_tika_content,
                normalized_seen=normalized_seen,
            )
            normalized = _normalize_text(text)
            if normalized and normalized not in normalized_seen:
                supplement = f"--- {candidate.label} ---\n{text.strip()}"
                supplements.append(supplement)
                normalized_seen.add(normalized)
                total_chars += len(supplement)
            if total_chars >= needed_chars:
                return DocumentOcrResult(
                    outcome=DocumentOcrOutcome.SUCCEEDED,
                    supplements=tuple(supplements),
                    page_count=page_count,
                    complete=False,
                )
        if not supplements and not tika_content.strip():
            return DocumentOcrResult(
                outcome=DocumentOcrOutcome.FAILED,
                page_count=page_count,
                complete=False,
            )
        return DocumentOcrResult(
            outcome=DocumentOcrOutcome.SUCCEEDED,
            supplements=tuple(supplements),
            page_count=page_count,
        )


def _ocr_raster_candidate(
    path: str,
    preprocessor: ImagePreprocessor | None,
    timeout_seconds: float,
    ocr_language: str,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        try:
            variants = _preprocess_image(image, preprocessor)
            try:
                best_text = ""
                best_text_size = 0
                for variant in variants:
                    remaining_seconds = deadline - time.monotonic()
                    if remaining_seconds <= 0:
                        raise TimeoutError("Document OCR timed out.")
                    text = ocr_tesseract_image_to_text(
                        variant,
                        ocr_language=ocr_language,
                        timeout_sec=max(0.001, remaining_seconds),
                    )
                    normalized = _normalize_text(text)
                    normalized_size = len(normalized)
                    if normalized_size > best_text_size:
                        best_text = text
                        best_text_size = normalized_size
                return best_text
            finally:
                for variant in variants:
                    if variant is not image:
                        variant.close()
        finally:
            image.close()


def _preprocess_image(
    image: Image.Image,
    preprocessor: ImagePreprocessor | None,
) -> tuple[Image.Image, ...]:
    if preprocessor is None:
        return (image,)
    image_array = numpy.array(image)
    is_complex, _diagnostics = preprocessor.detect_complexity(image_array)
    processed_arrays = (
        preprocessor.preprocess_complex(image_array)
        if is_complex
        else (preprocessor.preprocess_simple(image_array),)
    )
    variants: list[Image.Image] = []
    try:
        for array in processed_arrays:
            variants.append(Image.fromarray(array))
    except HANDLED_RUNTIME_EXCEPTIONS:
        for variant in variants:
            variant.close()
        raise
    return tuple(variants)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _retain_novel_ocr_lines(
    value: str,
    *,
    normalized_tika_content: str,
    normalized_seen: set[str],
) -> str:
    normalized_value = _normalize_text(value)
    if not normalized_value:
        return ""
    if normalized_value in normalized_tika_content:
        return ""
    if any(normalized_value in previous for previous in normalized_seen):
        return ""
    novel_lines: list[str] = []
    retained_lines: set[str] = set()
    for line in value.splitlines():
        normalized_line = _normalize_text(line)
        if not normalized_line:
            continue
        if normalized_line in retained_lines:
            continue
        if normalized_line in normalized_tika_content:
            continue
        if any(normalized_line in previous for previous in normalized_seen):
            continue
        novel_lines.append(line.strip())
        retained_lines.add(normalized_line)
    return "\n".join(novel_lines)
