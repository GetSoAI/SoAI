"""SoAI - MCP web scraper parsing utilities [backend/mcp/rag/scraper/parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.content_types import content_type_extension
from core.files.temp_files import create_secure_temp_file_descriptor
from core.files.types import ParsedDocument, ParseExecutionContext
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from mcp.rag.scraper.content_detection import is_json, is_textual, is_xml_text
from mcp.rag.scraper.html_decoding import decode_bytes_to_text
from mcp.rag.scraper.types import MARKDOWN_TYPES, FetchedContent

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = (
    "decode_rfc5987_value",
    "decode_text",
    "decoded_text_content",
    "extension_from_content_disposition",
    "extension_from_url",
    "infer_extension",
    "parse_with_registered_parser",
    "remove_file",
    "write_temp_file",
)

LOGGER_NAME = "SoAI.mcp.rag.parsing"
OPERATION_PARSER_TEMP_FILE = "mcp.rag.web_fetch.parser_temp_file"
PARSER_TEMP_WRITE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


def extension_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    suffix = os.path.splitext(parsed.path)[1] if parsed.path else ""
    return suffix.lstrip(".").lower() if suffix else None


def decode_rfc5987_value(value: str) -> str:
    cleaned = value.strip().strip('"')
    if "''" in cleaned:
        cleaned = cleaned.split("''", 1)[1]
    return unquote(cleaned)


def extension_from_content_disposition(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = [segment.strip() for segment in header_value.split(";") if segment.strip()]
    filename: str | None = None
    for segment in parts[1:]:
        key, separator, value = segment.partition("=")
        if not separator:
            continue
        key_lower = key.strip().lower()
        value = value.strip()
        if key_lower == "filename*":
            filename = decode_rfc5987_value(value)
            break
        if key_lower == "filename":
            filename = value.strip('"')
            break
    if not filename:
        return None
    suffix = os.path.splitext(filename)[1]
    return suffix.lstrip(".").lower() if suffix else None


def infer_extension(
    self: WebContentFetcherProtocol,
    final_url: str,
    content_type: str,
    sniffed_type: str,
    content_disposition: str | None,
) -> str | None:
    for candidate in (
        extension_from_url(final_url),
        extension_from_content_disposition(content_disposition),
        content_type_extension(content_type),
        content_type_extension(sniffed_type),
    ):
        if candidate and candidate in self.parsers:
            return candidate
    return None


def write_temp_file(
    data: bytes,
    extension: str | None,
    storage_manager: StorageManagerProtocol,
    source_url: str,
) -> str:
    required_bytes = len(data)
    if required_bytes <= 0:
        raise ValidationError("Fetched parser content is empty.")
    suffix = f".{extension}" if extension else ""
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=None,
        prefix="soai-",
        suffix=suffix,
    )
    try:
        with (
            storage_manager.reserve_disk_space(
                path=temp_path,
                required_bytes=required_bytes,
                operation=OPERATION_PARSER_TEMP_FILE,
                details={
                    "source_url": source_url,
                    "required_bytes": required_bytes,
                },
            ) as reservation,
            claim_reserved_write(reservation, size_bytes=required_bytes),
        ):
            with os.fdopen(file_descriptor, "wb") as temp_file:
                file_descriptor = -1
                temp_file.write(data)
    except PARSER_TEMP_WRITE_EXCEPTIONS:
        _close_temp_descriptor(file_descriptor)
        remove_file(temp_path)
        raise
    return temp_path


def _close_temp_descriptor(file_descriptor: int) -> None:
    if file_descriptor < 0:
        return
    try:
        os.close(file_descriptor)
    except OSError as error:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Failed to close parser temp file descriptor.",
            operation=OPERATION_PARSER_TEMP_FILE,
            level="debug",
        )


def remove_file(path: str) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError as error:
        logger.debug("Failed to remove temp file %s: %s", path, str(error))


def decode_text(self: WebContentFetcherProtocol, data: bytes, charset_hint: str | None) -> str:
    return decode_bytes_to_text(data, charset_hint=charset_hint, detector=self.charset_detector)


def decoded_text_content(
    self: WebContentFetcherProtocol,
    data: bytes,
    charset_hint: str | None,
    classification: str,
    source_url: str,
) -> FetchedContent:
    return FetchedContent(
        content=decode_text(self, data, charset_hint),
        content_type=classification,
        source_url=source_url,
    )


async def parse_with_registered_parser(
    self: WebContentFetcherProtocol,
    data: bytes,
    extension: str,
    content_type_hint: str | None,
    final_url: str,
) -> FetchedContent:
    parser = self.parsers.get(extension)
    if not parser:
        raise ValidationError(f"No parser registered for .{extension}")
    temp_file = await asyncio.to_thread(
        write_temp_file,
        data,
        extension,
        self.storage_manager,
        final_url,
    )
    try:
        parsed: ParsedDocument = await parser.parse(
            ParseExecutionContext(
                source_path=temp_file,
                cancellation_token=None,
                progress_callback=None,
                display_name=f"source.{extension}",
                extraction_deadline=time.monotonic() + LONG_IDLE_TIMEOUT_SEC,
            ),
        )
    finally:
        await asyncio.to_thread(remove_file, temp_file)
    if not parsed.content.strip():
        raise ValidationError(f"Parsed .{extension} content is empty")
    metadata: JSONDict = parsed.metadata or {}
    resolved_type = extension
    if content_type_hint:
        if is_json(content_type_hint):
            resolved_type = "json"
        elif content_type_hint in MARKDOWN_TYPES:
            resolved_type = "markdown"
        elif is_xml_text(content_type_hint):
            resolved_type = "xml"
        elif is_textual(content_type_hint):
            resolved_type = "text"
    elif extension in {"txt", "text", "log"}:
        resolved_type = "text"
    elif extension in {"json", "jsonl", "ndjson"}:
        resolved_type = "json"
    elif extension in {"md", "markdown", "mkdn", "mkd", "mdx"}:
        resolved_type = "markdown"
    title_value = metadata.get("title")
    if not isinstance(title_value, str):
        title_value = metadata.get("name")
    title = title_value if isinstance(title_value, str) and title_value else None
    return FetchedContent(
        content=parsed.content,
        content_type=resolved_type,
        title=title,
        page_count=parsed.page_count,
        source_url=final_url,
    )
