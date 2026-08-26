"""SoAI - URL normalization and local URL checks [backend/core/network/urls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from urllib.parse import ParseResult, urlparse, urlsplit, urlunsplit

from core.errors.exceptions import ValidationError
from core.network.hosts import normalize_host
from core.network.ip import is_local_network_ip

__all__ = (
    "build_host_port_url",
    "format_host_for_url",
    "format_host_port_netloc",
    "is_local_url",
    "normalize_base_url",
    "normalize_http_url",
    "parse_http_url_host_port",
    "redact_url_for_logging",
    "replace_url_host",
    "require_absolute_http_url",
)


def format_host_for_url(host: str) -> str:
    host_text = str(host or "").strip()
    if not host_text:
        raise ValidationError("Host cannot be empty.")
    if host_text.startswith("[") and host_text.endswith("]"):
        return host_text
    if ":" in host_text:
        return f"[{host_text}]"
    return host_text


def format_host_port_netloc(host: str, port: int) -> str:
    return f"{format_host_for_url(host)}:{int(port)}"


def build_host_port_url(scheme: str, host: str, port: int) -> str:
    scheme_text = str(scheme or "").strip().lower()
    if not scheme_text:
        raise ValidationError("URL scheme cannot be empty.")
    return f"{scheme_text}://{format_host_port_netloc(host, port)}"


def replace_url_host(url: str, host: str) -> str:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exception:
        raise ValidationError(f"URL port is invalid: {exception}") from exception
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    userinfo = ""
    if "@" in parsed.netloc:
        userinfo = f"{parsed.netloc.rsplit('@', maxsplit=1)[0]}@"
    netloc = f"{userinfo}{format_host_port_netloc(host, port)}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def is_local_url(target: str, *, parser: Callable[[str], ParseResult] = urlparse) -> bool:
    try:
        parsed = parser(target)
    except (ValueError, TypeError, AttributeError):
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = normalize_host(parsed.hostname)
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        return False
    return is_local_network_ip(ip_obj)


def normalize_http_url(url: str) -> str:
    return require_absolute_http_url(url, infer_https=True)


def parse_http_url_host_port(url: str, *, infer_https: bool = False) -> tuple[str, int]:
    normalized = require_absolute_http_url(url, infer_https=infer_https)
    try:
        parsed = urlparse(normalized)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    try:
        host = parsed.hostname
    except ValueError as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    if not host:
        raise ValidationError("URL must include a hostname.")
    normalized_host = host.lower().strip()
    if not normalized_host:
        raise ValidationError("URL must include a hostname.")
    try:
        explicit_port = parsed.port
    except ValueError as exception:
        raise ValidationError(f"URL port is invalid: {exception}") from exception
    scheme = parsed.scheme.lower()
    port = explicit_port or (443 if scheme == "https" else 80)
    return (normalized_host, port)


def require_absolute_http_url(url: str, *, infer_https: bool = False) -> str:
    if not isinstance(url, str):
        raise ValidationError("URL must be a string.")
    normalized = url.strip()
    if not normalized:
        raise ValidationError("URL cannot be empty.")
    try:
        parsed = urlparse(normalized)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    if infer_https and not parsed.scheme:
        normalized = f"https://{normalized}"
        try:
            parsed = urlparse(normalized)
        except (AttributeError, TypeError, ValueError) as exception:
            raise ValidationError(f"URL is invalid: {exception}") from exception
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValidationError(f"URL must use http or https scheme, got: {scheme!r}.")
    if not parsed.netloc:
        raise ValidationError("URL must include a network location.")
    try:
        host = parsed.hostname
        _ = parsed.port
    except ValueError as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    if not host:
        raise ValidationError("URL must include a hostname.")
    return normalized


def normalize_base_url(url: str) -> str:
    normalized = normalize_http_url(url)
    while normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def redact_url_for_logging(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return "<redacted>"
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "<redacted>"
    scheme = str(parsed.scheme or "").strip()
    host = str(parsed.hostname or "").strip()
    if not scheme or not host:
        return "<redacted>"
    try:
        port = parsed.port
    except ValueError:
        return "<redacted>"
    host_token = f"[{host}]" if ":" in host and not host.startswith("[") else host
    netloc = host_token if port is None else f"{host_token}:{int(port)}"
    return urlunsplit((scheme, netloc, str(parsed.path or ""), "", ""))
