"""SoAI - Scraper HTML link and media URL normalization [backend/mcp/rag/scraper/html_url_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

__all__ = (
    "absolutize_links_and_media",
    "absolutize_srcset",
    "extract_base_url",
    "is_relative_url",
)


def extract_base_url(soup: BeautifulSoup, origin_url: str) -> str:
    base_tag = soup.find(name="base", attrs={"href": True})
    if not base_tag:
        return origin_url
    base_href = base_tag.get("href")
    if not isinstance(base_href, str) or not base_href.strip():
        return origin_url
    resolved = urljoin(origin_url, base_href.strip())
    parsed = urlparse(resolved)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return origin_url
    return resolved


def is_relative_url(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "data:")):
        return False
    return True


def absolutize_srcset(srcset: str, base_url: str) -> str:
    parts: list[str] = []
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        url_token = tokens[0]
        rest = " ".join(tokens[1:])
        if is_relative_url(url_token):
            url_token = urljoin(base_url, url_token)
        parts.append(f"{url_token} {rest}".strip())
    return ", ".join(parts)


def absolutize_links_and_media(root: Tag | BeautifulSoup, base_url: str) -> None:
    for tag in root.find_all(True):
        if tag.name == "a":
            href = tag.get("href")
            if isinstance(href, str) and is_relative_url(href):
                tag["href"] = urljoin(base_url, href)
        elif tag.name in {"img", "source", "video", "audio"}:
            src = tag.get("src")
            if isinstance(src, str) and is_relative_url(src):
                tag["src"] = urljoin(base_url, src)
            srcset = tag.get("srcset")
            if isinstance(srcset, str) and srcset.strip():
                tag["srcset"] = absolutize_srcset(srcset, base_url)
