"""SoAI - HTML metadata and excerpt extraction helpers [backend/core/web/html_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_value

__all__ = (
    "PageMetadata",
    "extract_html_text_excerpt",
    "extract_html_title",
    "extract_page_metadata",
    "format_metadata_block",
)

LOGGER_NAME = "SoAI.core.web.html_metadata"
OPERATION_EXTRACT_JSON_LD = "core.web.html_metadata.extract_from_json_ld"


@dataclass(frozen=True, slots=True)
class PageMetadata:
    description: str
    author: str
    published_date: str
    site_name: str
    thumbnail_url: str


def _meta_content(soup: BeautifulSoup, attr_key: str, attr_value: str) -> str:
    tag = soup.find(name="meta", attrs={attr_key: attr_value})
    if not tag:
        return ""
    raw = tag.get("content")
    return str(raw).strip() if raw else ""


def _extract_from_json_ld(soup: BeautifulSoup, field: str) -> str:
    logger = get_logger(LOGGER_NAME)
    for script_tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script_tag.get_text(strip=True)
        if not text:
            continue
        try:
            data = parse_json_value(text)
        except (ValidationError, ValueError):
            continue
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to parse JSON-LD block (non-critical).",
                operation=OPERATION_EXTRACT_JSON_LD,
                level="debug",
            )
            continue
        if not isinstance(data, dict):
            continue
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, dict):
                name = first.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return ""


def extract_html_title(soup: BeautifulSoup, default_title: str) -> str:
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(" ", strip=True)
        if title_text:
            return title_text
    for attr_key, attr_value in (
        ("property", "og:title"),
        ("name", "twitter:title"),
        ("name", "title"),
    ):
        meta = soup.find(name="meta", attrs={attr_key: attr_value})
        if meta:
            value_raw = meta.get("content")
            value = (str(value_raw) if value_raw else "").strip()
            if value:
                return value
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(" ", strip=True)
        if h1_text:
            return h1_text
    return default_title


def extract_page_metadata(soup: BeautifulSoup) -> PageMetadata:
    description = (
        _meta_content(soup, "property", "og:description")
        or _meta_content(soup, "name", "description")
        or _meta_content(soup, "name", "twitter:description")
    )
    author = (
        _meta_content(soup, "name", "author")
        or _meta_content(soup, "property", "article:author")
        or _extract_from_json_ld(soup, "author")
    )
    published_date = (
        _meta_content(soup, "property", "article:published_time")
        or _extract_from_json_ld(soup, "datePublished")
        or _meta_content(soup, "name", "date")
    )
    site_name = _meta_content(soup, "property", "og:site_name")
    thumbnail_url = (
        _meta_content(soup, "property", "og:image")
        or _meta_content(soup, "property", "og:image:secure_url")
        or _meta_content(soup, "name", "twitter:image")
        or _meta_content(soup, "name", "twitter:image:src")
        or _extract_from_json_ld(soup, "image")
    )
    return PageMetadata(
        description=description,
        author=author,
        published_date=published_date,
        site_name=site_name,
        thumbnail_url=thumbnail_url,
    )


def format_metadata_block(metadata: PageMetadata) -> str:
    parts: list[str] = []
    if metadata.description:
        parts.append(f"Description: {metadata.description}")
    detail_segments: list[str] = []
    if metadata.author:
        detail_segments.append(f"Author: {metadata.author}")
    if metadata.published_date:
        detail_segments.append(f"Published: {metadata.published_date}")
    if metadata.site_name:
        detail_segments.append(f"Site: {metadata.site_name}")
    if detail_segments:
        parts.append(" | ".join(detail_segments))
    return "\n".join(parts)


def extract_html_text_excerpt(*, html_text: str, max_chars: int) -> str:
    if not isinstance(html_text, str):
        raise ValidationError("html_text must be a string.")
    if max_chars <= 0:
        raise ValidationError("max_chars must be positive.")
    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup.find_all(["script", "style", "noscript", "template"]):
        node.decompose()
    text = soup.get_text(" ", strip=True)
    normalized = re.sub(r"\s{2,}", " ", text).strip()
    if not normalized:
        return ""
    return normalized[:max_chars]
