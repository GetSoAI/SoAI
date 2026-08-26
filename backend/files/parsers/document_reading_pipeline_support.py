"""SoAI - Document reading pipeline support operations [backend/files/parsers/document_reading_pipeline_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.content_types import content_type_extension
from core.files.extraction_state import ExtractionState
from core.files.protocols import FileParserProtocol
from core.files.types import ParsedDocument, ParseExecutionContext
from core.logging.protocols import StandardLogger
from core.types.json import JSONDict, JSONValue, is_json_dict, is_json_value

__all__ = (
    "MetadataNormalizationResult",
    "ParseAttempt",
    "normalize_metadata",
    "remaining_timeout_sec",
    "select_parser",
    "try_parse_document",
)


@dataclass(frozen=True, slots=True)
class ParseAttempt:
    document: ParsedDocument
    parser_used: str


@dataclass(frozen=True, slots=True)
class MetadataNormalizationResult:
    metadata: JSONDict | None
    warnings: tuple[str, ...]


async def try_parse_document(
    logger: StandardLogger,
    *,
    extension: str,
    detected_mime: str,
    parser_registry: dict[str, FileParserProtocol],
    timeout_sec: float,
    warnings: list[str],
    operation: str,
    context: ParseExecutionContext,
) -> ParseAttempt:
    if timeout_sec <= 0:
        warnings.append("Parser skipped: shared parse timeout exhausted.")
        return ParseAttempt(
            document=ParsedDocument(content="", extraction_state=ExtractionState.TIMED_OUT),
            parser_used="",
        )
    parser = select_parser(parser_registry, extension, detected_mime)
    if parser is None:
        warnings.append(
            f"No parser available for this file type. extension={extension or 'unknown'}, mime={detected_mime or 'unknown'}.",
        )
        return ParseAttempt(
            document=ParsedDocument(content="", extraction_state=ExtractionState.UNSUPPORTED),
            parser_used="",
        )
    try:
        document = await asyncio.wait_for(parser.parse(context), timeout=timeout_sec)
        return ParseAttempt(document=document, parser_used=parser.__class__.__name__)
    except TaskCancelledError:
        raise
    except (TimeoutError, SoAITimeoutError):
        warnings.append(f"Parser timed out after {timeout_sec:.0f}s: {parser.__class__.__name__}")
        return ParseAttempt(
            document=ParsedDocument(content="", extraction_state=ExtractionState.TIMED_OUT),
            parser_used=parser.__class__.__name__,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Document parser failed.",
            operation=operation,
            details={"path": context.source_path, "parser": parser.__class__.__name__},
            level="warning",
        )
        warnings.append(f"Parser failed: {parser.__class__.__name__}.")
    return ParseAttempt(
        document=ParsedDocument(content="", extraction_state=ExtractionState.FAILED),
        parser_used=parser.__class__.__name__,
    )


def select_parser(
    parser_registry: dict[str, FileParserProtocol],
    extension: str,
    detected_mime: str,
) -> FileParserProtocol | None:
    if extension:
        parser = parser_registry.get(extension)
        if parser is not None:
            return parser
    inferred = content_type_extension(detected_mime)
    if inferred:
        parser = parser_registry.get(inferred)
        if parser is not None:
            return parser
    return None


def normalize_metadata(metadata: JSONDict | None) -> MetadataNormalizationResult:
    if metadata is None:
        return MetadataNormalizationResult(metadata=None, warnings=())
    if is_json_dict(metadata):
        return MetadataNormalizationResult(metadata=metadata, warnings=())
    if not isinstance(metadata, dict):
        return MetadataNormalizationResult(
            metadata=None,
            warnings=("Metadata dropped: parser returned non-object metadata.",),
        )
    normalized: dict[str, JSONValue] = {}
    dropped_items = 0
    for key, value in metadata.items():
        if not isinstance(key, str):
            dropped_items += 1
            continue
        if not is_json_value(value):
            dropped_items += 1
            continue
        normalized[key] = value
    if dropped_items:
        return MetadataNormalizationResult(
            metadata=normalized,
            warnings=(f"Metadata normalized; dropped {dropped_items} non-JSON values.",),
        )
    return MetadataNormalizationResult(metadata=normalized, warnings=())


def remaining_timeout_sec(*, start_time: float, timeout_sec: float) -> float:
    elapsed = time.monotonic() - start_time
    return timeout_sec - elapsed
