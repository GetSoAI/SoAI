"""SoAI - Extracted archive content parsing [backend/files/parsers/archive_content_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.extraction_state import ExtractionState
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.protocols import FileParserProtocol
from core.files.types import ParseExecutionContext
from core.logging.trace import get_logger
from files.parsers.archive_file_collection import collect_extracted_files

__all__ = ("ArchiveContentParseResult", "parse_extracted_archive_contents")

LOGGER_NAME = "SoAI.files.parsers.archive_content_parser"
OPERATION = "files.archive.parse_member"


_ARCHIVE_ENTRY_LISTING_LIMIT = 200


@dataclass(frozen=True, slots=True)
class ArchiveContentParseResult:
    content_parts: tuple[str, ...]
    extraction_state: ExtractionState
    warnings: tuple[str, ...]


async def parse_extracted_archive_contents(
    temp_dir: str,
    parsers: dict[str, FileParserProtocol],
    exclude_extensions: frozenset[str],
    archive_type: str,
    *,
    parent_context: ParseExecutionContext,
) -> ArchiveContentParseResult:
    logger = get_logger(LOGGER_NAME)
    extracted_files = collect_extracted_files(temp_dir)
    content_parts: list[str] = []
    listing_lines = [
        f"Archive type: {archive_type}",
        f"Entries: {len(extracted_files)}",
        "Files:",
    ]
    max_listed = _ARCHIVE_ENTRY_LISTING_LIMIT
    for relative_path, _ in extracted_files[:max_listed]:
        listing_lines.append(f"- {relative_path}")
    if len(extracted_files) > max_listed:
        listing_lines.append(f"- ... ({len(extracted_files) - max_listed} more)")
    content_parts.append("\n".join(listing_lines))
    incomplete_members = 0
    for relative_path, extracted_path in extracted_files:
        raise_if_parse_cancelled(parent_context)
        file_extension = relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else ""
        if file_extension in exclude_extensions:
            continue
        parser = parsers.get(file_extension)
        if parser is None:
            continue
        try:
            parsed = await parser.parse(
                parent_context.with_source(extracted_path, relative_path),
            )
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Archive member parser failed (non-critical).",
                operation=OPERATION,
                details={"archive_type": archive_type, "relative_path": relative_path},
                level="debug",
            )
            content_parts.append(
                f"## File: {relative_path}\n\nParsing failed.",
            )
            incomplete_members += 1
            continue
        if parsed.extraction_state is not ExtractionState.COMPLETE:
            incomplete_members += 1
        if parsed.content.strip():
            content_parts.append(f"## File: {relative_path}\n\n{parsed.content}")
    warnings = (
        (f"Archive member extraction was incomplete for {incomplete_members} entries.",)
        if incomplete_members
        else ()
    )
    return ArchiveContentParseResult(
        content_parts=tuple(content_parts),
        extraction_state=(
            ExtractionState.DEGRADED if incomplete_members else ExtractionState.COMPLETE
        ),
        warnings=warnings,
    )
