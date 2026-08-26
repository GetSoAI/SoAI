"""SoAI - URL normalization and site scoping [backend/core/web/site_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Required, TypedDict
from urllib.parse import SplitResult, urlsplit

import idna

from core.network.urls import format_host_for_url, format_host_port_netloc

__all__ = (
    "OriginScope",
    "ParsedSite",
    "assert_url_allowed",
    "normalize_url",
    "site_scope_from_url",
)


@dataclass(frozen=True, slots=True)
class ParsedSite:
    scheme: str
    host: str
    port: int | None
    origin: str


class OriginScope(TypedDict):
    scope_type: Required[Literal["origin"]]
    origin: Required[str]


if TYPE_CHECKING:
    type SiteScope = OriginScope
else:
    SiteScope = OriginScope


def normalize_url(url: str) -> ParsedSite:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower().strip()
    if scheme not in {"http", "https"}:
        raise ValueError("URL scheme must be http or https.")

    parsed_hostname = parsed.hostname
    if parsed_hostname is None:
        raise ValueError("URL must include a hostname.")

    normalized_host = _canonicalize_hostname(parsed_hostname)
    port = _read_explicit_port(parsed)
    origin = _build_origin(scheme=scheme, host=normalized_host, port=port)

    return ParsedSite(
        scheme=scheme,
        host=normalized_host,
        port=port,
        origin=origin,
    )


def site_scope_from_url(url: str) -> SiteScope:
    parsed_site = normalize_url(url)
    return OriginScope(scope_type="origin", origin=parsed_site.origin)


def assert_url_allowed(current_page_url: str, scope: SiteScope) -> None:
    current = normalize_url(current_page_url)
    expected_origin = scope["origin"]
    if current.origin != expected_origin:
        raise ValueError("Current page is outside the required origin scope.")


def _canonicalize_hostname(hostname: str) -> str:
    normalized = hostname.strip().lower()
    if normalized == "":
        raise ValueError("URL hostname must not be empty.")
    try:
        return idna.encode(normalized).decode("ascii")
    except idna.IDNAError as exception:
        raise ValueError("URL hostname is not valid IDNA.") from exception


def _read_explicit_port(parsed: SplitResult) -> int | None:
    try:
        return parsed.port
    except ValueError as exception:
        raise ValueError("URL port is invalid.") from exception


def _build_origin(*, scheme: str, host: str, port: int | None) -> str:
    if port is None:
        return f"{scheme}://{format_host_for_url(host)}"
    return f"{scheme}://{format_host_port_netloc(host, port)}"
