"""SoAI - HTML to markdown conversion with optimized settings [backend/mcp/rag/scraper/markdown_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
import re

from bs4 import BeautifulSoup, Tag

from mcp.rag.scraper.markdown_rendering import render_html_fragment_to_markdown

__all__ = (
    "convert_html_to_markdown",
    "detect_code_language",
    "resolve_lazy_images",
)

_LANGUAGE_CLASS_PATTERN_SOURCE: str = r"(?:language|lang|highlight|brush|code)-(\w[\w+#.-]*)"
_LANGUAGE_CLASS_PATTERN_FLAGS: int = re.IGNORECASE


@functools.cache
def _language_class_pattern() -> re.Pattern[str]:
    return re.compile(_LANGUAGE_CLASS_PATTERN_SOURCE, _LANGUAGE_CLASS_PATTERN_FLAGS)


_LAZY_SRC_ATTRS: tuple[str, ...] = (
    "data-src",
    "data-lazy-src",
    "data-original",
    "data-lazy",
    "data-url",
)

_PLACEHOLDER_INDICATORS: tuple[str, ...] = (
    "data:image/",
    "blank.",
    "placeholder",
    "spacer",
    "pixel",
    "loading.",
    "spinner",
)


def _extract_language_from_classes(node: Tag) -> str:
    raw_class = node.get("class")
    if not raw_class:
        return ""
    pattern = _language_class_pattern()
    class_list: list[str] = raw_class if isinstance(raw_class, list) else [raw_class]
    for class_name in class_list:
        match = pattern.search(str(class_name))
        if match:
            return match.group(1).lower()
    return ""


def detect_code_language(element: Tag) -> str:
    for node in (element, element.parent):
        if not isinstance(node, Tag):
            continue
        result = _extract_language_from_classes(node)
        if result:
            return result
    for child in element.find_all("code", recursive=False):
        if isinstance(child, Tag):
            result = _extract_language_from_classes(child)
            if result:
                return result
    return ""


def _src_is_placeholder(src_value: str) -> bool:
    if not src_value:
        return True
    lowered = src_value.lower().strip()
    if not lowered:
        return True
    return any(indicator in lowered for indicator in _PLACEHOLDER_INDICATORS)


def resolve_lazy_images(root: Tag | BeautifulSoup) -> None:
    for img in root.find_all("img"):
        current_src = img.get("src")
        current_src_str = str(current_src).strip() if current_src else ""
        if not _src_is_placeholder(current_src_str):
            continue
        for attr in _LAZY_SRC_ATTRS:
            lazy_value = img.get(attr)
            if isinstance(lazy_value, str) and lazy_value.strip():
                img["src"] = lazy_value.strip()
                break
        lazy_srcset = img.get("data-srcset")
        if not isinstance(lazy_srcset, str) or not lazy_srcset.strip():
            continue
        existing_srcset = img.get("srcset")
        if not existing_srcset or not str(existing_srcset).strip():
            img["srcset"] = lazy_srcset.strip()


def convert_html_to_markdown(html_str: str) -> str:
    return render_html_fragment_to_markdown(
        html_str,
        code_language_resolver=detect_code_language,
    )
