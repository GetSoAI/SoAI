"""SoAI - MCP web scraper content type detection [backend/mcp/rag/scraper/content_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.content_types import parse_content_type
from core.logging.trace import get_logger
from mcp.rag.scraper.types import HTML_TYPES, JSON_TYPES, MARKDOWN_TYPES, XML_TYPES

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = (
    "is_json",
    "is_markdown",
    "is_textual",
    "is_xml_text",
    "looks_binary",
    "matches_html_signature",
    "matches_json_signature",
    "matches_pdf_signature",
    "matches_xml_signature",
    "normalize_vendor_type",
    "resolve_effective_type",
    "should_treat_as_html",
    "sniff_type",
    "split_content_type",
)

LOGGER_NAME = "SoAI.mcp.rag.content_detection"
OPERATION = "mcp.rag.scraper.content_detection.sniff_type"


def split_content_type(value: str) -> tuple[str, dict[str, str]]:
    parsed = parse_content_type(value)
    return (parsed.value, parsed.parameters)


def normalize_vendor_type(value: str) -> str:
    if not value:
        return ""
    if value.endswith("+json"):
        return "application/json"
    if value.endswith("+xml"):
        return "application/xml"
    return value


def matches_html_signature(data: bytes) -> bool:
    snippet = data[:512].lower()
    return any(token in snippet for token in (b"<!doctype html", b"<html", b"<body", b"<head"))


def matches_pdf_signature(data: bytes) -> bool:
    return data.startswith(b"%PDF")


def matches_json_signature(data: bytes) -> bool:
    stripped = data.lstrip()
    return stripped.startswith(b"{") or stripped.startswith(b"[")


def matches_xml_signature(data: bytes) -> bool:
    snippet = data[:512].lstrip().lower()
    xml_tokens = (b"<?xml", b"<rss", b"<feed", b"<rdf", b"<svg")
    return any(snippet.startswith(token) for token in xml_tokens)


def looks_binary(data: bytes) -> bool:
    sample = data[:1024]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    printable = sum(
        1 for byte_value in sample if 32 <= byte_value <= 126 or byte_value in (9, 10, 13)
    )
    return printable / len(sample) < 0.6


def resolve_effective_type(reported: str, sniffed: str) -> str:
    if sniffed and (not reported or reported in {"application/octet-stream", "text/plain"}):
        return sniffed
    if reported in XML_TYPES and sniffed == "text/html":
        return "text/html"
    return reported or sniffed


def sniff_type(
    self: WebContentFetcherProtocol,
    data: bytes,
) -> str:
    logger = get_logger(LOGGER_NAME)
    if matches_pdf_signature(data):
        return "application/pdf"
    if matches_html_signature(data):
        return "text/html"
    if matches_json_signature(data):
        return "application/json"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"
    if data.startswith(b"\x1f\x8b"):
        return "application/x-gzip"
    if data.startswith(b"BZh"):
        return "application/x-bzip2"
    if data.startswith(b"\xfd7zXZ\x00"):
        return "application/x-xz"
    if data.startswith(b"Rar!\x1a\x07\x00") or data.startswith(b"Rar!\x1a\x07\x01"):
        return "application/x-rar-compressed"
    if data.startswith(b"7z\xbc\xaf'\x1c"):
        return "application/x-7z-compressed"
    if data.startswith(b"(\xb5/\xfd"):
        return "application/zstd"
    if matches_xml_signature(data):
        return "application/xml"
    detector = self.magic_detector
    if detector is not None:
        try:
            detected = detector.from_buffer(data[:4096])
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to detect MIME type via local detector (non-critical).",
                operation=OPERATION,
                level="debug",
            )
            detected = None
        if detected:
            return str(detected).lower()
    return ""


def should_treat_as_html(content_type: str, data: bytes) -> bool:
    if content_type in HTML_TYPES:
        return True
    if content_type in XML_TYPES:
        return matches_html_signature(data)
    if not content_type:
        return matches_html_signature(data)
    return False


def is_markdown(content_type: str) -> bool:
    return content_type in MARKDOWN_TYPES


def is_json(content_type: str) -> bool:
    if not content_type:
        return False
    if content_type in JSON_TYPES:
        return True
    return content_type.endswith("+json")


def is_xml_text(content_type: str) -> bool:
    return content_type in XML_TYPES


def is_textual(content_type: str) -> bool:
    return bool(content_type and content_type.startswith("text/"))
