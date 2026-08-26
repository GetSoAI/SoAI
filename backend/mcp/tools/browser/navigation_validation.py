"""SoAI - Browser tool navigation validation [backend/mcp/tools/browser/navigation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from core.errors.exceptions import ValidationError
from core.network.urls import normalize_http_url
from mcp.tools.error import MCPToolError

__all__ = ("build_navigation_url_candidates",)


def build_navigation_url_candidates(url: str) -> tuple[str, str | None]:
    normalized = str(url or "").strip()
    if not normalized:
        raise MCPToolError(-32602, "url must be a non-empty string")
    parsed_raw = urlparse(normalized)
    raw_scheme = (parsed_raw.scheme or "").lower()
    if raw_scheme == "about":
        if (parsed_raw.path or "").lower() != "blank":
            raise MCPToolError(-32602, "Only about:blank is supported for about: navigation.")
        return (normalized, None)
    if normalized.lower().startswith("data:"):
        if len(normalized) > 1_000_000:
            raise MCPToolError(-32602, "data: url is too long")
        return (normalized, None)
    if raw_scheme and raw_scheme not in {"http", "https"}:
        return (normalized, None)
    try:
        normalized = normalize_http_url(normalized)
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    parsed = urlparse(normalized)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise MCPToolError(-32602, "url must start with http:// or https://")
    if not parsed.netloc.strip():
        raise MCPToolError(-32602, "url must include a hostname")
    if raw_scheme in {"http", "https"}:
        return (normalized, None)
    https_url = urlunparse(parsed._replace(scheme="https"))
    http_url = urlunparse(parsed._replace(scheme="http"))
    fallback_url = http_url if http_url != https_url else None
    return (https_url, fallback_url)
