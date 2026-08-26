"""SoAI - PDF font manifest loading [backend/core/browser/pdf_font_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_text
from core.meta.paths import get_repo_root, join_data_abs
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.strings import require_trimmed_json_text

__all__ = (
    "PdfFontEntry",
    "PdfFontRange",
    "load_pdf_font_manifest",
    "resolve_pdf_font_cache_root",
    "resolve_pdf_font_manifest_path",
    "resolve_pdf_font_source_root",
)

_FONT_ROOT_RELATIVE = ("frontend", "assets", "fonts")
_FONT_CACHE_RELATIVE = ("temp", "pdf-font-cache")
_MANIFEST_NAME = "pdf-font-manifest.json"


@dataclass(frozen=True, slots=True)
class PdfFontRange:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PdfFontEntry:
    relative_path: str
    family: str
    style: str
    weight: str
    priority: int
    sha256: str
    size_bytes: int
    ranges: tuple[PdfFontRange, ...]


def resolve_pdf_font_source_root() -> str:
    return os.path.join(get_repo_root(), *_FONT_ROOT_RELATIVE)


def resolve_pdf_font_cache_root() -> str:
    return join_data_abs(get_repo_root(), *_FONT_CACHE_RELATIVE)


def resolve_pdf_font_manifest_path() -> str:
    return os.path.join(resolve_pdf_font_source_root(), _MANIFEST_NAME)


def _require_string(value: JSONValue, field: str) -> str:
    return require_trimmed_json_text(
        value,
        error_message=f"PDF font manifest field '{field}' must be a non-empty string.",
    )


def _require_int(value: JSONValue, field: str) -> int:
    if not is_strict_int(value):
        raise ValidationError(f"PDF font manifest field '{field}' must be an integer.")
    return value


def _parse_range(value: JSONValue) -> PdfFontRange:
    if not isinstance(value, list) or len(value) != 2:
        raise ValidationError("PDF font manifest ranges must contain two integers.")
    start = _require_int(value[0], "ranges.start")
    end = _require_int(value[1], "ranges.end")
    if start < 0 or end < start:
        raise ValidationError("PDF font manifest range is invalid.")
    return PdfFontRange(start=start, end=end)


def _parse_entry(value: JSONValue) -> PdfFontEntry:
    if not isinstance(value, dict):
        raise ValidationError("PDF font manifest entry must be an object.")
    ranges_value = value.get("ranges")
    if not isinstance(ranges_value, list):
        raise ValidationError("PDF font manifest entry ranges must be a list.")
    relative_path = _require_string(value.get("path"), "path")
    if os.path.isabs(relative_path) or ".." in relative_path.replace("\\", "/").split("/"):
        raise ValidationError("PDF font manifest path is invalid.")
    return PdfFontEntry(
        relative_path=relative_path,
        family=_require_string(value.get("family"), "family"),
        style=_require_string(value.get("style"), "style"),
        weight=_require_string(value.get("weight"), "weight"),
        priority=_require_int(value.get("priority"), "priority"),
        sha256=_require_string(value.get("sha256"), "sha256").lower(),
        size_bytes=_require_int(value.get("size_bytes"), "size_bytes"),
        ranges=tuple(_parse_range(item) for item in ranges_value),
    )


def load_pdf_font_manifest() -> tuple[PdfFontEntry, ...]:
    manifest_path = resolve_pdf_font_manifest_path()
    with open_text(manifest_path, mode="r", encoding="utf-8", errors="strict") as handle:
        manifest = parse_json_dict(handle.read(), field="pdf_font_manifest")
    if _require_int(manifest.get("version"), "version") != 1:
        raise ValidationError("PDF font manifest version is unsupported.")
    fonts_value = manifest.get("fonts")
    if not isinstance(fonts_value, list):
        raise ValidationError("PDF font manifest fonts must be a list.")
    entries = tuple(_parse_entry(item) for item in fonts_value)
    if not entries:
        raise ValidationError("PDF font manifest has no fonts.")
    return tuple(sorted(entries, key=lambda entry: entry.priority))
