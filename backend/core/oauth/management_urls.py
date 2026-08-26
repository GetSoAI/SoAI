"""SoAI - Shared OAuth management URL helpers [backend/core/oauth/management_urls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.network.urls import normalize_base_url
from core.system_api.route_paths import (
    MCP_OAUTH_CALLBACK_PATH,
    MCP_OAUTH_CLIENT_METADATA_PATH,
)

__all__ = (
    "build_mcp_oauth_urls",
    "build_oauth_urls",
    "require_https_url",
    "resolve_mcp_oauth_callback_url",
    "resolve_mcp_public_client_metadata_url",
    "resolve_oauth_public_origin",
    "resolve_public_client_metadata_url",
)


def require_https_url(url: str, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValidationError(f"{label} must use https.")
    if not parsed.netloc:
        raise ValidationError(f"{label} must be an absolute URL.")
    try:
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exception:
        raise ValidationError(f"{label} is invalid: {exception}") from exception
    if not hostname:
        raise ValidationError(f"{label} must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError(f"{label} must not include credentials.")
    if any(character.isspace() for character in parsed.netloc):
        raise ValidationError(f"{label} contains an invalid hostname.")


def build_oauth_urls(
    base_url: str,
    *,
    callback_path: str,
    client_metadata_path: str,
) -> tuple[str, str]:
    normalized = normalize_base_url(base_url)
    callback_url = f"{normalized}{callback_path}"
    client_metadata_url = f"{normalized}{client_metadata_path}"
    return callback_url, client_metadata_url


def build_mcp_oauth_urls(base_url: str) -> tuple[str, str]:
    return build_oauth_urls(
        base_url,
        callback_path=MCP_OAUTH_CALLBACK_PATH,
        client_metadata_path=MCP_OAUTH_CLIENT_METADATA_PATH,
    )


def resolve_oauth_public_origin(configured_base_url: str) -> str:
    configured = str(configured_base_url or "").strip()
    if not configured:
        raise ValidationError("SERVER.PUBLIC_ORIGIN is not configured.")
    parsed = urlparse(configured)
    if parsed.scheme.lower() != "https":
        raise ValidationError("SERVER.PUBLIC_ORIGIN must use https.")
    normalized = normalize_base_url(configured)
    require_https_url(normalized, "SERVER.PUBLIC_ORIGIN")
    normalized_parsed = urlparse(normalized)
    if normalized_parsed.path not in {"", "/"} or normalized_parsed.params:
        raise ValidationError("SERVER.PUBLIC_ORIGIN must not include a path.")
    if normalized_parsed.query or normalized_parsed.fragment:
        raise ValidationError("SERVER.PUBLIC_ORIGIN must not include a query or fragment.")
    return normalized


def resolve_public_client_metadata_url(
    *,
    configured_base_url: str,
    client_metadata_path: str,
) -> str | None:
    configured = str(configured_base_url or "").strip()
    if not configured:
        return None
    base_url = resolve_oauth_public_origin(configured)
    _, client_metadata_url = build_oauth_urls(
        base_url,
        callback_path=MCP_OAUTH_CALLBACK_PATH,
        client_metadata_path=client_metadata_path,
    )
    return client_metadata_url


def resolve_mcp_oauth_callback_url(
    *,
    configured_base_url: str,
) -> str:
    callback_base_url = resolve_oauth_public_origin(configured_base_url)
    callback_url, _ = build_mcp_oauth_urls(callback_base_url)
    return callback_url


def resolve_mcp_public_client_metadata_url(*, configured_base_url: str) -> str | None:
    return resolve_public_client_metadata_url(
        configured_base_url=configured_base_url,
        client_metadata_path=MCP_OAUTH_CLIENT_METADATA_PATH,
    )
