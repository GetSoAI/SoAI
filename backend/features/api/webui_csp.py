"""SoAI - WebUI content security policy builder [backend/features/api/webui_csp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import Scope

from core.bootstrap.discovery_ports import DISCOVERY_PORTS
from core.network.urls import format_host_for_url

__all__ = ("build_webui_content_security_policy",)

WEBUI_CSP_STATIC_DIRECTIVES: tuple[str, ...] = (
    "default-src 'self'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "frame-src https://www.youtube-nocookie.com",
    "form-action 'self'",
    "script-src 'self'",
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "media-src 'self' blob:",
    "object-src 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
)


def build_webui_content_security_policy(nonce: str, scope: Scope | None) -> str:
    directives = [
        *WEBUI_CSP_STATIC_DIRECTIVES,
        f"style-src 'self' blob: 'nonce-{nonce}'",
        _build_connect_src_directive(scope),
    ]
    return "; ".join(directives)


def _build_connect_src_directive(scope: Scope | None) -> str:
    sources = ["'self'"]
    host = _resolve_scope_hostname(scope)
    scheme = _resolve_scope_scheme(scope)
    if host is not None:
        for port in DISCOVERY_PORTS:
            sources.append(f"{scheme}://{host}:{port}")
    return f"connect-src {' '.join(sources)}"


def _resolve_scope_scheme(scope: Scope | None) -> str:
    if scope is None:
        return "http"
    raw_scheme = scope.get("scheme")
    if raw_scheme == "https":
        return "https"
    return "http"


def _resolve_scope_hostname(scope: Scope | None) -> str | None:
    host_header = _resolve_host_header(scope)
    if host_header is not None:
        return _normalize_csp_host(host_header)
    server = scope.get("server") if scope is not None else None
    if isinstance(server, tuple) and server and isinstance(server[0], str) and server[0].strip():
        return _normalize_csp_host(server[0].strip())
    return None


def _resolve_host_header(scope: Scope | None) -> str | None:
    if scope is None:
        return None
    host_header = Headers(scope=scope).get("host")
    if host_header is None:
        return None
    normalized = host_header.strip()
    return normalized or None


def _normalize_csp_host(host: str) -> str | None:
    stripped = host.strip()
    if not stripped or any(ord(character) <= 32 for character in stripped):
        return None
    try:
        parsed = urlsplit(f"//{stripped}")
        _ = parsed.port
    except ValueError:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if parsed.path or parsed.query or parsed.fragment:
        return None
    if not parsed.hostname:
        return None
    return format_host_for_url(parsed.hostname)
