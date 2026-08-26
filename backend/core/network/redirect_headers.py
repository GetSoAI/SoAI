"""SoAI - HTTP redirect header safety helpers [backend/core/network/redirect_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse

__all__ = ("headers_for_redirect",)

SENSITIVE_REDIRECT_HEADERS = frozenset(("authorization", "cookie", "proxy-authorization"))


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
