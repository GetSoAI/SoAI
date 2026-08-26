"""SoAI - Shared MCP resource URI builders [backend/mcp/shared/resource_uris.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlencode

__all__ = ("build_resource_uri",)


def build_resource_uri(
    *,
    base_uri: str,
    path: str,
    query_items: tuple[tuple[str, str | int | None], ...],
) -> str:
    normalized_query_items = sorted(
        [
            (key, str(value))
            for key, value in query_items
            if value is not None and str(value).strip()
        ],
        key=lambda item: item[0],
    )
    if not normalized_query_items:
        return f"{base_uri}{path}"
    return f"{base_uri}{path}?{urlencode(normalized_query_items)}"
