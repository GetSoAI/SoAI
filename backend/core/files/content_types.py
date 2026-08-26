"""SoAI - Shared MIME and content-type normalization helpers [backend/core/files/content_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import mimetypes
from dataclasses import dataclass

__all__ = (
    "ParsedContentType",
    "content_type_extension",
    "content_type_is_audio",
    "content_type_is_document",
    "content_type_is_html",
    "content_type_is_image",
    "content_type_is_javascript",
    "content_type_is_text",
    "content_type_is_video",
    "normalize_content_type",
    "parse_content_type",
    "resolve_content_type_charset",
)

DOCUMENT_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/rtf",
        "text/rtf",
        "application/epub+zip",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.presentationml.template",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    },
)
TEXT_CONTENT_TYPES: frozenset[str] = frozenset(
    {"application/json", "application/xml", "application/x-yaml", "text/xml"},
)
JAVASCRIPT_CONTENT_TYPES: frozenset[str] = frozenset(
    {"application/ecmascript", "application/javascript", "text/ecmascript", "text/javascript"},
)
EXTENSION_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("application/msword", "doc"),
    ("application/epub+zip", "epub"),
    ("application/json", "json"),
    ("application/rar", "rar"),
    ("application/octet-stream", ""),
    ("application/pdf", "pdf"),
    ("application/rtf", "rtf"),
    ("application/vnd.ms-excel", "xls"),
    ("application/vnd.ms-powerpoint", "ppt"),
    ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ("application/x-7z-compressed", "7z"),
    ("application/x-bzip2", "bz2"),
    ("application/x-gzip", "gz"),
    ("application/x-mobipocket-ebook", "mobi"),
    ("application/x-rar-compressed", "rar"),
    ("application/x-tar", "tar"),
    ("application/x-xz", "xz"),
    ("application/x-zip-compressed", "zip"),
    ("application/x-zstd-compressed", "zst"),
    ("application/xhtml+xml", "xhtml"),
    ("application/zip", "zip"),
    ("application/zstd", "zst"),
    ("image/bmp", "bmp"),
    ("image/jpeg", "jpg"),
    ("image/png", "png"),
    ("image/tiff", "tiff"),
    ("image/webp", "webp"),
    ("text/csv", "csv"),
    ("text/html", "html"),
    ("text/json", "json"),
    ("text/markdown", "md"),
    ("text/plain", "txt"),
    ("text/yaml", "yaml"),
)


@dataclass(frozen=True, slots=True)
class ParsedContentType:
    value: str
    parameters: dict[str, str]


def normalize_content_type(value: str | None) -> str:
    raw = str(value or "")
    return raw.split(";", 1)[0].strip().lower()


def parse_content_type(value: str | None) -> ParsedContentType:
    raw = str(value or "")
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    if not parts:
        return ParsedContentType(value="", parameters={})
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        key, separator, parameter_value = part.partition("=")
        if not separator:
            continue
        parameters[key.strip().lower()] = parameter_value.strip().strip('"')
    return ParsedContentType(value=parts[0].lower(), parameters=parameters)


def resolve_content_type_charset(value: str | None, *, default: str = "utf-8") -> str:
    parsed = parse_content_type(value)
    charset = parsed.parameters.get("charset")
    if charset:
        return charset.strip().lower() or default
    return default


def content_type_is_html(value: str | None) -> bool:
    return normalize_content_type(value) in {"application/xhtml+xml", "text/html"}


def content_type_is_javascript(value: str | None) -> bool:
    return normalize_content_type(value) in JAVASCRIPT_CONTENT_TYPES


def content_type_is_image(value: str | None) -> bool:
    normalized = normalize_content_type(value)
    return normalized.startswith("image/") and normalized != "image/svg+xml"


def content_type_is_audio(value: str | None) -> bool:
    return normalize_content_type(value).startswith("audio/")


def content_type_is_video(value: str | None) -> bool:
    return normalize_content_type(value).startswith("video/")


def content_type_is_text(value: str | None) -> bool:
    normalized = normalize_content_type(value)
    return normalized.startswith("text/") or normalized in TEXT_CONTENT_TYPES


def content_type_is_document(value: str | None) -> bool:
    normalized = normalize_content_type(value)
    if not normalized or normalized == "application/octet-stream":
        return False
    if normalized == "pdf" or normalized in DOCUMENT_CONTENT_TYPES:
        return True
    if normalized.startswith("application/vnd.openxmlformats-officedocument."):
        return True
    return normalized.startswith("application/vnd.oasis.opendocument.")


def content_type_extension(value: str | None) -> str | None:
    normalized = normalize_content_type(value)
    if not normalized:
        return None
    for content_type, extension in EXTENSION_OVERRIDES:
        if content_type == normalized:
            return extension or None
    guessed = mimetypes.guess_extension(normalized, strict=False)
    if guessed:
        return guessed.lstrip(".").lower()
    if normalized.endswith("+json"):
        return "json"
    if normalized.endswith("+xml"):
        return "xml"
    if normalized.endswith("+zip"):
        return "zip"
    if normalized.startswith("image/"):
        return "png"
    if normalized.startswith("text/"):
        return "txt"
    return None
