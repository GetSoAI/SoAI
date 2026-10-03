"""SoAI - HTTP redirect safety helpers [backend/core/network/redirect_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urljoin, urlparse

import httpx2

from core.network.errors import HTTPDownloadRedirectError
from core.network.urls import normalize_http_url

__all__ = ("REDIRECT_STATUS_CODES", "headers_for_redirect", "resolve_redirect_url")

REDIRECT_STATUS_CODES = frozenset((301, 302, 303, 307, 308))
SENSITIVE_REDIRECT_HEADERS = frozenset(("authorization", "cookie", "proxy-authorization"))


def resolve_redirect_url(response: httpx2.Response, current_url: str) -> str | None:
    if response.status_code not in REDIRECT_STATUS_CODES:
        return None
    location = response.headers.get("Location")
    if not location:
        raise HTTPDownloadRedirectError(
            "Server sent a redirect response without a Location header.",
        )
    return normalize_http_url(urljoin(current_url, location))


def headers_for_redirect(
    headers: Mapping[str, str] | None,
    *,
    previous_url: str,
    next_url: str,
) -> dict[str, str] | None:
    if headers is None:
        return None
    if _same_origin(previous_url, next_url):
        return dict(headers)
    return {
        header_name: header_value
        for header_name, header_value in headers.items()
        if header_name.lower() not in SENSITIVE_REDIRECT_HEADERS
    }


def _same_origin(previous_url: str, next_url: str) -> bool:
    previous = urlparse(previous_url)
    current = urlparse(next_url)
    return (
        previous.scheme.lower(),
        previous.hostname or "",
        _normalized_port(previous.scheme, previous.port),
    ) == (
        current.scheme.lower(),
        current.hostname or "",
        _normalized_port(current.scheme, current.port),
    )


def _normalized_port(scheme: str, port: int | None) -> int | None:
    if port is not None:
        return port
    normalized_scheme = scheme.lower()
    if normalized_scheme == "http":
        return 80
    if normalized_scheme == "https":
        return 443
    return None
