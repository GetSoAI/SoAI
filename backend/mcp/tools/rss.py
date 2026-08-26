"""SoAI - MCP RSS feed reader tool implementation [backend/mcp/tools/rss.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

import httpx2
from defusedxml import ElementTree

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.network.urls import require_absolute_http_url
from mcp.tools.argument_fields import (
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.argument_scalars import parse_clamped_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.offline_policy import require_url_allowed_when_offline

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_rss_read",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"url", "max_items"})


async def tool_rss_read(self: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    url_value = get_arg(arguments, "url")
    if isinstance(url_value, bytes | bytearray):
        url_value = url_value.decode("utf-8", errors="replace")
    url = require_non_empty_string(
        url_value,
        key="url",
        type_message=f"url must be a string, got {type(url_value).__name__}",
        empty_message="url must not be empty",
    )
    max_items = parse_clamped_int(
        arguments.get("max_items"),
        field_name="max_items",
        default=10,
        min_value=1,
        max_value=100,
    )
    try:
        require_absolute_http_url(url)
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    await require_url_allowed_when_offline(
        self.runtime_flags,
        tool_name="rss_read",
        url=url,
        capability="rss_read fetch",
    )
    max_rss_size = 10 * MIB_BYTES
    web_fetcher = self.web_fetcher
    if not web_fetcher:
        raise MCPToolError(-32603, "Web fetcher not available")
    try:
        content_bytes, _, _, _ = await web_fetcher.fetch_raw(url, offline_source="RSS feed fetch")
        if len(content_bytes) > max_rss_size:
            raise MCPToolError(
                -32603,
                f"RSS feed content too large: {len(content_bytes)} bytes exceeds {max_rss_size} limit",
            )
        content = content_bytes.decode("utf-8", errors="replace")
    except (ValueError, httpx2.HTTPError) as exception:
        raise MCPToolError(-32603, f"RSS feed fetch failed: {exception}") from exception
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exception:
        raise MCPToolError(-32602, f"Invalid XML: {exception}") from exception
    feed_title, feed_link, feed_description = ("", "", "")
    items: list[dict[str, str]] = []
    channel = root.find("channel")
    if channel is not None:
        feed_title = (channel.findtext("title") or "").strip()
        feed_link = (channel.findtext("link") or "").strip()
        feed_description = (channel.findtext("description") or "").strip()
        for item in channel.findall("item")[:max_items]:
            items.append(
                {
                    "title": unescape((item.findtext("title") or "").strip()),
                    "link": (item.findtext("link") or "").strip(),
                    "description": unescape((item.findtext("description") or "").strip()),
                    "published": (item.findtext("pubDate") or "").strip(),
                    "author": (
                        item.findtext("author")
                        or item.findtext("{http://purl.org/dc/elements/1.1/}creator")
                        or ""
                    ).strip(),
                },
            )
    else:
        items = _parse_atom_feed(root, max_items)
        feed_title, feed_link, feed_description = _extract_atom_feed_metadata(root)
    return {
        "feed_title": feed_title,
        "feed_link": feed_link,
        "feed_description": feed_description,
        "items": items,
        "item_count": len(items),
    }


def _extract_atom_feed_metadata(
    root: Element,
) -> tuple[str, str, str]:
    xml_namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    feed_title = (
        root.findtext("atom:title", namespaces=xml_namespaces) or root.findtext("title") or ""
    ).strip()
    link_el = root.find("atom:link[@rel='alternate']", namespaces=xml_namespaces)
    if link_el is None:
        link_el = root.find("atom:link", namespaces=xml_namespaces)
    if link_el is None:
        link_el = root.find("link")
    feed_link = (link_el.get("href") if link_el is not None else "") or ""
    feed_description = (
        root.findtext("atom:subtitle", namespaces=xml_namespaces) or root.findtext("subtitle") or ""
    ).strip()
    return feed_title, feed_link, feed_description


def _parse_atom_feed(root: Element, max_items: int) -> list[dict[str, str]]:
    xml_namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, str]] = []
    entries = root.findall("atom:entry", namespaces=xml_namespaces)
    if not entries:
        entries = root.findall("entry")
    for entry in entries[:max_items]:
        title = (
            entry.findtext("atom:title", namespaces=xml_namespaces) or entry.findtext("title") or ""
        )
        link_el = entry.find("atom:link[@rel='alternate']", namespaces=xml_namespaces)
        if link_el is None:
            link_el = entry.find("atom:link", namespaces=xml_namespaces)
        if link_el is None:
            link_el = entry.find("link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        summary = (
            entry.findtext("atom:summary", namespaces=xml_namespaces)
            or entry.findtext("atom:content", namespaces=xml_namespaces)
            or entry.findtext("summary")
            or entry.findtext("content")
            or ""
        )
        published = (
            entry.findtext("atom:published", namespaces=xml_namespaces)
            or entry.findtext("atom:updated", namespaces=xml_namespaces)
            or entry.findtext("published")
            or entry.findtext("updated")
            or ""
        )
        author_el = entry.find("atom:author/atom:name", namespaces=xml_namespaces)
        if author_el is None:
            author_el = entry.find(
                "{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name",
            )
        if author_el is None:
            author_el = entry.find("author/name")
        author = (author_el.text if author_el is not None else "") or ""
        items.append(
            {
                "title": unescape(title.strip()),
                "link": link.strip(),
                "description": unescape(summary.strip()),
                "published": published.strip(),
                "author": author.strip(),
            },
        )
    return items
