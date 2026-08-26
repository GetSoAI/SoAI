"""SoAI - Discovery CORS validation [backend/app/lifecycle/discovery_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlparse

__all__ = ("resolve_discovery_cors_origin",)


def resolve_discovery_cors_origin(origin: str | None, *, host_header: str | None) -> str | None:
    if not origin:
        return None
    origin_text = origin.strip()
    if not origin_text:
        return None
    if origin_text == "null":
        return "null"
    parsed = urlparse(origin_text)
    if parsed.scheme not in {"http", "https"}:
        return None
    origin_host = parsed.hostname
    if not origin_host:
        return None
    host_text = (host_header or "").strip()
    host_name: str | None = None
    if host_text:
        if host_text.startswith("[") and "]" in host_text:
            host_name = host_text[1 : host_text.index("]")]
        else:
            host_name = host_text.split(":", 1)[0]
        host_name = host_name.strip() or None
    allowed_hosts = {host for host in (host_name, "localhost", "127.0.0.1", "::1") if host}
    if origin_host in allowed_hosts:
        return origin_text
    return None
