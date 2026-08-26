"""SoAI - Proxy header parsing and real client IP resolution [backend/core/runtime/proxy_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from collections.abc import Mapping

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.runtime.state_access import read_state_flag
from core.runtime.trusted_proxy import (
    is_trusted_proxy_client_host,
    read_trusted_proxy_networks,
)

__all__ = (
    "client_is_trusted_proxy",
    "collect_forwarded_chain",
    "extract_real_client_ip",
    "normalize_scheme_value",
    "parse_forwarded_proto",
    "parse_x_forwarded_proto",
    "resolve_client_ip_from_chain",
    "resolve_request_scheme",
    "split_forwarded_tokens",
)

LOGGER_NAME = "SoAI.core.runtime.proxy_headers"
OPERATION_CORE_RUNTIME_PROXY_HEADERS_RESOLVE_REQUEST_SCHEME_URL = (
    "core_runtime.proxy_headers.resolve_request_scheme.url"
)
OPERATION_CORE_RUNTIME_PROXY_HEADERS_RESOLVE_REQUEST_SCHEME_URL_SCHEME = (
    "core_runtime.proxy_headers.resolve_request_scheme.url_scheme"
)


def split_forwarded_tokens(header_value: str | None) -> tuple[str, ...]:
    if not header_value:
        return ()
    return tuple(token.strip() for token in header_value.split(",") if token.strip())


def _normalize_forwarded_ip_token(token: str | None) -> str | None:
    if not token:
        return None
    text = token.strip().strip('"').strip("'")
    if not text or text.lower() in {"unknown", "obfuscated"}:
        return None
    if text.startswith("["):
        closing = text.find("]")
        if closing >= 0:
            text = text[1:closing]
    elif ":" in text and text.count(":") == 1 and ("." in text):
        host_part, port_part = text.rsplit(":", 1)
        if port_part.isdigit():
            text = host_part
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return None
    return text


def _extract_forwarded_parameters(header_value: str | None, target_key: str) -> tuple[str, ...]:
    if not header_value:
        return ()
    entries: list[str] = []
    target = f"{target_key.lower()}="
    for token in split_forwarded_tokens(header_value):
        parts = token.split(";")
        for part in parts:
            text = part.strip()
            if text.lower().startswith(target):
                value = text.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    entries.append(value)
    return tuple(entries)


def collect_forwarded_chain(headers: Mapping[str, str] | None) -> tuple[str, ...]:
    mapping = headers or {}
    header_chain = split_forwarded_tokens(mapping.get("x-forwarded-for"))
    if not header_chain:
        header_chain = _extract_forwarded_parameters(mapping.get("forwarded"), "for")
    normalized: list[str] = []
    for entry in header_chain:
        normalized_entry = _normalize_forwarded_ip_token(entry)
        if normalized_entry:
            normalized.append(normalized_entry)
    return tuple(normalized)


def resolve_client_ip_from_chain(
    direct_host: str | None,
    headers: Mapping[str, str],
    trusted_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    proxy_enabled: bool,
) -> str | None:
    if not direct_host:
        return None
    if not proxy_enabled or not trusted_networks:
        return direct_host
    try:
        client_ip_obj = ipaddress.ip_address(direct_host)
    except ValueError:
        return direct_host
    if not any(client_ip_obj in network for network in trusted_networks):
        return direct_host
    chain = list(collect_forwarded_chain(headers))
    normalized_host = _normalize_forwarded_ip_token(direct_host)
    chain.append(normalized_host or direct_host)
    for entry in chain:
        try:
            ip_obj = ipaddress.ip_address(entry)
        except ValueError:
            continue
        if any(ip_obj in network for network in trusted_networks):
            continue
        return entry
    return direct_host


def extract_real_client_ip(request: RequestProtocol) -> str | None:
    client = request.client
    host = client.host if client else None
    if not host:
        return None
    app = request.app
    if app is None:
        return host
    state = app.state
    proxy_enabled = read_state_flag(state, "proxy_headers_enabled")
    networks = read_trusted_proxy_networks(state) or ()
    return resolve_client_ip_from_chain(host, request.headers, networks, proxy_enabled)


def normalize_scheme_value(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered in {"http", "https"}:
        return lowered
    if lowered == "ws":
        return "http"
    if lowered == "wss":
        return "https"
    return None


def parse_x_forwarded_proto(header_value: str | None) -> str | None:
    for token in split_forwarded_tokens(header_value):
        candidate = normalize_scheme_value(token)
        if candidate:
            return candidate
    return None


def parse_forwarded_proto(header_value: str | None) -> str | None:
    for value in _extract_forwarded_parameters(header_value, "proto"):
        candidate = normalize_scheme_value(value)
        if candidate:
            return candidate
    return None


def resolve_request_scheme(request: RequestProtocol) -> str:
    if client_is_trusted_proxy(request):
        forwarded_proto = parse_x_forwarded_proto(request.headers.get("x-forwarded-proto"))
        if forwarded_proto:
            return forwarded_proto
        forwarded = parse_forwarded_proto(request.headers.get("forwarded"))
        if forwarded:
            return forwarded
    scope = request.scope
    scope_scheme = scope.get("scheme") if isinstance(scope, dict) else None
    scheme = normalize_scheme_value(scope_scheme if isinstance(scope_scheme, str) else None)
    if scheme:
        return scheme
    try:
        url_value = request.url
    except KeyError as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="core_runtime.proxy_headers.resolve_request_scheme.url",
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to build request.url while resolving scheme (non-critical).",
            operation=OPERATION_CORE_RUNTIME_PROXY_HEADERS_RESOLVE_REQUEST_SCHEME_URL,
            level="debug",
        )
        url_value = None
    if url_value is None:
        url_scheme = None
    else:
        try:
            url_scheme = url_value.scheme
        except KeyError as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="core_runtime.proxy_headers.resolve_request_scheme.url_scheme",
            )
            log_handled_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Failed to read request.url.scheme while resolving scheme (non-critical).",
                operation=OPERATION_CORE_RUNTIME_PROXY_HEADERS_RESOLVE_REQUEST_SCHEME_URL_SCHEME,
                level="debug",
            )
            url_scheme = None
    scheme = normalize_scheme_value(url_scheme)
    if scheme:
        return scheme
    raise StateError("Request scheme could not be resolved from headers or scope.")


def client_is_trusted_proxy(request: RequestProtocol) -> bool:
    app = request.app
    if app is None:
        return False
    client = request.client
    host = client.host if client else None
    return is_trusted_proxy_client_host(app, host)
