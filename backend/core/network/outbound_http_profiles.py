"""SoAI - Shared outbound HTTP request header profiles [backend/core/network/outbound_http_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

__all__ = (
    "DEFAULT_BROWSER_ACCEPT_LANGUAGE",
    "DEFAULT_BROWSER_DOCUMENT_USER_AGENTS",
    "build_artifact_download_headers",
    "build_browser_asset_headers",
    "build_browser_document_headers",
    "build_default_browser_asset_headers",
    "build_github_api_headers",
    "build_model_registry_headers",
    "build_outbound_request_headers",
    "build_service_outbound_headers",
    "merge_outbound_headers",
)

DEFAULT_BROWSER_DOCUMENT_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
)
DEFAULT_BROWSER_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
SOAI_SERVICE_USER_AGENT = "SoAI (+https://soai.to)"
GITHUB_API_ACCEPT = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"


def _require_header_value(*, header_name: str, value: str) -> str:
    normalized_value = str(value).strip()
    if not normalized_value:
        raise ValueError(f"{header_name} cannot be empty.")
    return normalized_value


def build_service_outbound_headers(*, user_agent: str) -> dict[str, str]:
    return {"User-Agent": _require_header_value(header_name="User-Agent", value=user_agent)}


def build_browser_document_headers(
    *,
    user_agent: str,
    accept: str,
    accept_language: str,
) -> dict[str, str]:
    return {
        "User-Agent": _require_header_value(header_name="User-Agent", value=user_agent),
        "Accept": _require_header_value(header_name="Accept", value=accept),
        "Accept-Language": _require_header_value(
            header_name="Accept-Language",
            value=accept_language,
        ),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


def build_browser_asset_headers(
    *,
    user_agent: str,
    accept_language: str,
) -> dict[str, str]:
    return build_browser_document_headers(
        user_agent=user_agent,
        accept="*/*",
        accept_language=accept_language,
    )


def build_default_browser_asset_headers() -> dict[str, str]:
    return build_browser_asset_headers(
        user_agent=DEFAULT_BROWSER_DOCUMENT_USER_AGENTS[0],
        accept_language=DEFAULT_BROWSER_ACCEPT_LANGUAGE,
    )


def merge_outbound_headers(
    base_headers: Mapping[str, str],
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    header_names_by_lower: dict[str, str] = {}
    for source in (base_headers, extra_headers or {}):
        for raw_name, raw_value in source.items():
            header_name = str(raw_name).strip()
            header_value = str(raw_value).strip()
            if not header_name:
                raise ValueError("HTTP header name cannot be empty.")
            if not header_value:
                raise ValueError(f"HTTP header '{header_name}' cannot be empty.")
            lowered_name = header_name.lower()
            previous_name = header_names_by_lower.get(lowered_name)
            if previous_name is not None:
                del merged[previous_name]
            header_names_by_lower[lowered_name] = header_name
            merged[header_name] = header_value
    return merged


def build_github_api_headers(*, github_token: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": SOAI_SERVICE_USER_AGENT,
        "Accept": GITHUB_API_ACCEPT,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    normalized_token = github_token.strip() if isinstance(github_token, str) else ""
    if normalized_token:
        headers["Authorization"] = f"Bearer {normalized_token}"
    return headers


def build_artifact_download_headers() -> dict[str, str]:
    return build_default_browser_asset_headers()


def build_model_registry_headers(*, bearer_token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
    }
    normalized_token = bearer_token.strip() if isinstance(bearer_token, str) else ""
    if normalized_token:
        headers["Authorization"] = f"Bearer {normalized_token}"
    return headers


def build_outbound_request_headers(
    *,
    profile_type: Literal[
        "artifact_download",
        "external_provider",
        "github_api",
        "model_registry_api",
        "neutral_runtime",
        "service_api",
    ],
    extra_headers: Mapping[str, str] | None = None,
    github_token: str | None = None,
    bearer_token: str | None = None,
) -> dict[str, str]:
    if profile_type == "artifact_download":
        base_headers = build_artifact_download_headers()
    elif profile_type == "external_provider":
        base_headers = {}
    elif profile_type == "github_api":
        base_headers = build_github_api_headers(github_token=github_token)
    elif profile_type == "model_registry_api":
        base_headers = build_model_registry_headers(bearer_token=bearer_token)
    elif profile_type == "neutral_runtime":
        base_headers = {}
    elif profile_type == "service_api":
        base_headers = build_service_outbound_headers(user_agent=SOAI_SERVICE_USER_AGENT)
    else:
        raise ValueError(f"Unsupported outbound HTTP profile type: {profile_type}")
    return merge_outbound_headers(base_headers, extra_headers)
