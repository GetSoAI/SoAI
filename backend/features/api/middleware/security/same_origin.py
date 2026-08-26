"""SoAI - Same-origin matching between Origin headers and request hosts [backend/features/api/middleware/security/same_origin.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlsplit

__all__ = ("origin_matches_request_host",)

ALLOWED_ORIGIN_SCHEMES: frozenset[str] = frozenset({"http", "https"})


def _default_port_for_scheme(scheme: str) -> int:
    if scheme in {"https", "wss"}:
        return 443
    return 80


def _split_host_header(host_header: str) -> tuple[str, int | None] | None:
    stripped = host_header.strip()
    if not stripped:
        return None
    try:
        parsed = urlsplit(f"//{stripped}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if not hostname:
        return None
    return (hostname, port)


def _split_origin(origin: str) -> tuple[str, str, int | None] | None:
    try:
        parsed = urlsplit(origin.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_ORIGIN_SCHEMES:
        return None
    if not hostname:
        return None
    return (scheme, hostname, port)


def origin_matches_request_host(
    origin: str,
    request_host: str | None,
    request_scheme: str | None,
) -> bool:
    if not request_host:
        return False
    host_parts = _split_host_header(request_host)
    if host_parts is None:
        return False
    origin_parts = _split_origin(origin)
    if origin_parts is None:
        return False
    origin_scheme, origin_hostname, origin_port = origin_parts
    request_hostname, request_port = host_parts
    if origin_hostname.lower() != request_hostname.lower():
        return False
    normalized_request_scheme = (request_scheme or "").strip().lower()
    if origin_port is None:
        origin_port = _default_port_for_scheme(origin_scheme)
    if request_port is None:
        request_port = _default_port_for_scheme(normalized_request_scheme)
    return origin_port == request_port
