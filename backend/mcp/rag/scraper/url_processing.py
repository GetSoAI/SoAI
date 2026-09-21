"""SoAI - MCP web scraper URL content processing [backend/mcp/rag/scraper/url_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_value
from mcp.rag.scraper.content_detection import (
    is_json,
    is_markdown,
    is_textual,
    is_xml_text,
    looks_binary,
    normalize_vendor_type,
    resolve_effective_type,
    should_treat_as_html,
    sniff_type,
    split_content_type,
)
from mcp.rag.scraper.html_parse_executor import get_html_parse_executor
from mcp.rag.scraper.html_processing import parse_html_blocking
from mcp.rag.scraper.json_cleaning import strip_json_noise_keys
from mcp.rag.scraper.parsing import (
    decode_text,
    decoded_text_content,
    infer_extension,
    parse_with_registered_parser,
)
from mcp.rag.scraper.types import FetchedContent

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = ("process_fetched_url_content",)


async def process_fetched_url_content(
    self: WebContentFetcherProtocol,
    *,
    ocr_language: str,
    content: bytes,
    content_type: str,
    final_url: str,
    content_disposition: str | None,
) -> FetchedContent:
    normalized_type, params = split_content_type(content_type)
    normalized_type = normalize_vendor_type(normalized_type)
    sniffed = sniff_type(self, content)
    effective_type = resolve_effective_type(normalized_type, sniffed)
    charset = params.get("charset")
    if should_treat_as_html(effective_type, content):
        try:
            return await run_bounded_blocking_call(
                get_html_parse_executor(),
                parse_html_blocking,
                content,
                final_url,
                self.html_parser,
                self.strip_link_urls,
                self.strip_images,
                timeout_sec=self.html_parse_timeout,
            )
        except TimeoutError as exception:
            raise ValidationError(
                f"HTML parsing timed out after {self.html_parse_timeout}s for {final_url}",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            raise ValidationError(
                f"Failed to parse HTML from {final_url}: {type(exception).__name__}: {exception}",
            ) from exception
    parser_extension = infer_extension(
        self,
        final_url,
        effective_type,
        sniffed,
        content_disposition,
    )
    if parser_extension:
        try:
            return await asyncio.wait_for(
                parse_with_registered_parser(
                    self,
                    content,
                    parser_extension,
                    effective_type,
                    final_url,
                    ocr_language=ocr_language,
                ),
                timeout=self.document_parse_timeout,
            )
        except TimeoutError as exception:
            raise ValidationError(
                f"Parsing .{parser_extension} content timed out after {self.document_parse_timeout}s (size: {len(content)} bytes)",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            raise ValidationError(
                f"Failed to parse .{parser_extension} content from {final_url}: {type(exception).__name__}: {exception}",
            ) from exception
    if is_json(effective_type):
        text = decode_text(self, content, charset)
        try:
            formatted = serialize_json_pretty_sorted_strict(
                strip_json_noise_keys(parse_json_value(text)),
                ensure_ascii=False,
            )
            return FetchedContent(content=formatted, content_type="json", source_url=final_url)
        except ValidationError:
            return FetchedContent(content=text, content_type="text", source_url=final_url)
    if is_markdown(effective_type):
        return decoded_text_content(self, content, charset, "markdown", final_url)
    if is_xml_text(effective_type) or sniffed == "application/xml":
        return decoded_text_content(self, content, charset, "xml", final_url)
    if is_textual(effective_type):
        return decoded_text_content(self, content, charset, "text", final_url)
    if not looks_binary(content):
        return decoded_text_content(self, content, charset, "text", final_url)
    raise ValidationError(
        f"Unsupported content type: {content_type or effective_type or 'unknown'}",
    )
