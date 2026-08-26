"""SoAI - HTML to markdown web scraper [backend/mcp/rag/scraper/html_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from core.web.html_metadata import (
    extract_html_title,
    extract_page_metadata,
    format_metadata_block,
)
from mcp.rag.scraper.html_boilerplate_removal import (
    remove_irrelevant_html,
)
from mcp.rag.scraper.html_decoding import decode_bytes_to_text
from mcp.rag.scraper.html_main_selection import select_main_html_node
from mcp.rag.scraper.html_url_normalization import (
    absolutize_links_and_media,
    extract_base_url,
)
from mcp.rag.scraper.markdown_conversion import (
    convert_html_to_markdown,
    resolve_lazy_images,
)
from mcp.rag.scraper.types import FetchedContent

__all__ = ("parse_html_blocking",)


def parse_html_blocking(
    html_bytes: bytes,
    url: str,
    html_parser: str,
    strip_link_urls: bool = False,
    strip_images: bool = False,
) -> FetchedContent:
    html_text = decode_bytes_to_text(html_bytes)
    soup = BeautifulSoup(html_text, html_parser)
    title_text = extract_html_title(soup, url)
    metadata = extract_page_metadata(soup)
    base_url = extract_base_url(soup, url)
    remove_irrelevant_html(soup)
    if not strip_images:
        resolve_lazy_images(soup)
    main_content = select_main_html_node(soup)
    if strip_link_urls:
        for anchor in main_content.find_all("a"):
            if anchor.has_attr("href"):
                del anchor["href"]
    if strip_images:
        for node in main_content.find_all(["img", "picture", "source", "video", "audio"]):
            node.decompose()
    if not strip_link_urls or not strip_images:
        absolutize_links_and_media(main_content, base_url)
    markdown_body = convert_html_to_markdown(str(main_content))
    normalized_body = re.sub("\\n{3,}", "\n\n", markdown_body).strip()
    if title_text:
        pattern = f"\\s*#\\s+{re.escape(title_text)}\\s*\\n+"
        normalized_body = re.sub(pattern, "", normalized_body, count=1).lstrip()
    metadata_block = format_metadata_block(metadata)
    header_parts = [f"# {title_text}", f"Source: {url}"]
    if metadata_block:
        header_parts.append(metadata_block)
    header_parts.append(f"\n{normalized_body.strip()}\n")
    combined = "\n\n".join(header_parts)
    return FetchedContent(
        content=combined,
        content_type="markdown",
        title=title_text,
        source_url=url,
        source_html=html_text,
    )
