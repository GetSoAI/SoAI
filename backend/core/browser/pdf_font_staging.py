"""SoAI - PDF font staging and stylesheet writing [backend/core/browser/pdf_font_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import cache

from core.browser.pdf_font_manifest import (
    PdfFontEntry,
    PdfFontRange,
    load_pdf_font_manifest,
    resolve_pdf_font_source_root,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_binary_writes import atomic_write_binary
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_binary
from core.serialization.base64_values import encode_base64_ascii

__all__ = ("prune_pdf_font_cache", "stage_pdf_fonts")

_BASE_FONT_COUNT = 6
_VARIATION_SELECTOR_RANGES = ((0xFE00, 0xFE0F), (0xE0100, 0xE01EF))
_COPY_CHUNK_BYTES = MIB_BYTES
_CACHE_FILE_PATTERN_SOURCE = r"^[0-9a-f]{64}\.[0-9A-Za-z]+$"


@cache
def _cache_file_pattern() -> re.Pattern[str]:
    return re.compile(_CACHE_FILE_PATTERN_SOURCE)


@dataclass(frozen=True, slots=True)
class _StagedPdfFont:
    entry: PdfFontEntry
    staged_path: str
    content: bytes


def _range_contains(font_range: PdfFontRange, codepoint: int) -> bool:
    return font_range.start <= codepoint <= font_range.end


def _entry_covers(entry: PdfFontEntry, codepoint: int) -> bool:
    return any(_range_contains(font_range, codepoint) for font_range in entry.ranges)


def _is_variation_selector(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in _VARIATION_SELECTOR_RANGES)


def _requires_font_coverage(character: str) -> bool:
    if not character.strip():
        return False
    codepoint = ord(character)
    if _is_variation_selector(codepoint):
        return False
    return unicodedata.category(character) != "Cf"


def _select_entries(entries: tuple[PdfFontEntry, ...], text: str) -> tuple[PdfFontEntry, ...]:
    selected: list[PdfFontEntry] = list(entries[:_BASE_FONT_COUNT])
    covered = {
        codepoint
        for entry in selected
        for font_range in entry.ranges
        for codepoint in range(font_range.start, font_range.end + 1)
    }
    wanted = {ord(character) for character in text if _requires_font_coverage(character)}
    missing = wanted.difference(covered)
    for entry in entries[_BASE_FONT_COUNT:]:
        matched = {codepoint for codepoint in missing if _entry_covers(entry, codepoint)}
        if not matched:
            continue
        selected.append(entry)
        missing.difference_update(matched)
        if not missing:
            break
    return tuple(selected)


def _cache_file_name(entry: PdfFontEntry) -> str:
    return f"{entry.sha256}{os.path.splitext(entry.relative_path)[1]}"


def _cache_font(
    source_path: str,
    cache_path: str,
    expected_sha256: str,
    expected_size_bytes: int,
) -> None:
    digest = hashlib.sha256()
    copied_size_bytes = 0

    def copy_verified_font(handle: io.BufferedIOBase) -> None:
        nonlocal copied_size_bytes
        with open_binary(source_path, mode="rb") as source:
            while True:
                chunk = source.read(_COPY_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
                copied_size_bytes += len(chunk)
        if copied_size_bytes != expected_size_bytes:
            raise ValidationError("PDF font asset size does not match the manifest.")
        if digest.hexdigest().lower() != expected_sha256:
            raise ValidationError("PDF font asset digest does not match the manifest.")

    atomic_write_binary(cache_path, copy_verified_font)


def _read_verified_font(path: str, entry: PdfFontEntry) -> bytes:
    with open_binary(path, mode="rb") as handle:
        content = handle.read()
    if len(content) != entry.size_bytes:
        raise ValidationError("PDF font cache size does not match the manifest.")
    if hashlib.sha256(content).hexdigest().lower() != entry.sha256:
        raise ValidationError("PDF font cache digest does not match the manifest.")
    return content


def _stage_font(entry: PdfFontEntry, source_root: str, cache_dir: str) -> _StagedPdfFont:
    source_path = os.path.join(source_root, entry.relative_path)
    if not os.path.isfile(source_path):
        raise ValidationError("PDF font asset is missing.")
    cache_path = os.path.join(cache_dir, _cache_file_name(entry))
    if not os.path.isfile(cache_path):
        _cache_font(source_path, cache_path, entry.sha256, entry.size_bytes)
    return _StagedPdfFont(
        entry=entry,
        staged_path=cache_path,
        content=_read_verified_font(cache_path, entry),
    )


def _font_mime_type(path: str) -> str:
    extension = os.path.splitext(path)[1].lower()
    if extension == ".woff2":
        return "font/woff2"
    if extension == ".ttf":
        return "font/ttf"
    if extension == ".ttc":
        return "font/collection"
    if extension == ".otf":
        return "font/otf"
    raise ValidationError("PDF font asset type is unsupported.")


def _font_data_uri(staged: _StagedPdfFont) -> str:
    mime_type = _font_mime_type(staged.staged_path)
    return f"data:{mime_type};base64,{encode_base64_ascii(staged.content)}"


def _format_ranges(ranges: tuple[PdfFontRange, ...]) -> str:
    return ", ".join(
        (
            f"U+{font_range.start:04X}"
            if font_range.start == font_range.end
            else f"U+{font_range.start:04X}-{font_range.end:04X}"
        )
        for font_range in ranges
    )


def _build_font_face(staged: _StagedPdfFont) -> str:
    entry = staged.entry
    return (
        "@font-face { "
        f'font-family: "{entry.family}"; '
        f'src: url("{_font_data_uri(staged)}"); '
        f"font-style: {entry.style}; "
        f"font-weight: {entry.weight}; "
        "font-display: block; "
        f"unicode-range: {_format_ranges(entry.ranges)}; "
        "}"
    )


def _build_stylesheet(staged_fonts: tuple[_StagedPdfFont, ...]) -> str:
    family_stack = ", ".join(f'"{font.entry.family}"' for font in staged_fonts)
    return "\n".join(
        (
            *(_build_font_face(font) for font in staged_fonts),
            f":root {{ --soai-pdf-font-sans: {family_stack}, sans-serif; }}",
            "html, body { font-family: var(--soai-pdf-font-sans) !important; }",
            "pre, code { font-family: var(--soai-pdf-font-sans) !important; }",
        ),
    )


def stage_pdf_fonts(*, text: str, cache_dir: str, css_path: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    entries = _select_entries(load_pdf_font_manifest(), text)
    source_root = resolve_pdf_font_source_root()
    staged = tuple(_stage_font(entry, source_root, cache_dir) for entry in entries)
    atomic_write_text_content(css_path, _build_stylesheet(staged))


def prune_pdf_font_cache(cache_dir: str) -> int:
    if not os.path.isdir(cache_dir):
        return 0
    published = {_cache_file_name(entry) for entry in load_pdf_font_manifest()}
    pattern = _cache_file_pattern()
    removed = 0
    for name in os.listdir(cache_dir):
        if name in published or not pattern.match(name):
            continue
        os.remove(os.path.join(cache_dir, name))
        removed += 1
    return removed
