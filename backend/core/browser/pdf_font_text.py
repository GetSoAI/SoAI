"""SoAI - PDF font text extraction [backend/core/browser/pdf_font_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from html.parser import HTMLParser
from typing import override

__all__ = ("extract_pdf_visible_text",)

_IGNORED_ELEMENTS = frozenset({"script", "style", "noscript", "template"})


class _PdfTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._parts: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag.lower() in _IGNORED_ELEMENTS:
            self._ignored_depth += 1

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _IGNORED_ELEMENTS and self._ignored_depth > 0:
            self._ignored_depth -= 1

    @override
    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0 and data:
            self._parts.append(data)

    def text(self) -> str:
        return "\n".join(self._parts)


def extract_pdf_visible_text(html_text: str) -> str:
    extractor = _PdfTextExtractor()
    extractor.feed(html_text)
    extractor.close()
    return extractor.text()
