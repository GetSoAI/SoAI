"""SoAI - System API request path matching helpers [backend/core/system_api/request_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from starlette.types import Scope

from core.system_api.route_paths import (
    ANTHROPIC_MESSAGES_PATH,
    MCP_API_PREFIX,
    MCP_ROOT_PATH,
    OPENAI_COMPAT_PREFIX,
    OPENAI_COMPAT_PREFIX_WITH_SLASH,
    PUBLIC_API_REQUESTS,
    SOAI_API_OPENAPI_SCHEMA_PATH,
    SOAI_WEBUI_WIZARD_COMPLETE_PATH,
    SOAI_WEBUI_WIZARD_EVALUATION_TERMS_PATH,
    SOAI_WEBUI_WIZARD_GOVERNING_DOCUMENTS_PREFIX,
    SOAI_WEBUI_WIZARD_PERSONAL_PURCHASE_TERMS_PATH,
    SOAI_WEBUI_WIZARD_STATUS_PATH,
)

__all__ = (
    "PublicRequestSurface",
    "get_scope_path",
    "is_anthropic_api_request_path",
    "is_mcp_request_path",
    "is_openai_api_request_path",
    "is_openai_compatibility_request_path",
    "is_public_inference_api_request_path",
    "is_wizard_bootstrap_endpoint",
    "is_wizard_status_endpoint",
    "normalize_request_path_for_match",
    "resolve_public_request_surface",
)

_PUBLIC_WEBUI_PATHS = frozenset(
    (
        "/",
        "/index.html",
        "/detached.html",
        "/favicon.ico",
        "/favicon-16x16.png",
        "/favicon-32x32.png",
        "/apple-touch-icon.png",
        "/android-chrome-192x192.png",
        "/android-chrome-512x512.png",
        "/manifest.webmanifest",
        "/robots.txt",
    )
)
_PUBLIC_WEBUI_PREFIX = "/assets"


class PublicRequestSurface(Enum):
    API = "api"
    WEBUI = "webui"


def get_scope_path(
    scope: Scope | Mapping[str, str | int | float | bool | bytes | None],
) -> str:
    path = scope.get("path")
    return path if isinstance(path, str) else ""


def normalize_request_path_for_match(path: str) -> str:
    return path.rstrip("/") or "/"


def _contains_decoded_dot_segment(path: str) -> bool:
    return any(segment in {".", ".."} for segment in path.split("/"))


def resolve_public_request_surface(
    path: str,
    method: str,
) -> PublicRequestSurface | None:
    normalized_path = normalize_request_path_for_match(path)
    normalized_method = method.upper()
    if (normalized_method, normalized_path) in PUBLIC_API_REQUESTS:
        return PublicRequestSurface.API
    if normalized_method not in {"GET", "HEAD"}:
        return None
    casefolded_path = normalized_path.casefold()
    if casefolded_path in _PUBLIC_WEBUI_PATHS:
        return PublicRequestSurface.WEBUI
    if _contains_decoded_dot_segment(normalized_path):
        return None
    if "\\" in normalized_path:
        return None
    if casefolded_path == _PUBLIC_WEBUI_PREFIX or casefolded_path.startswith(
        f"{_PUBLIC_WEBUI_PREFIX}/"
    ):
        return PublicRequestSurface.WEBUI
    return None


def is_openai_compatibility_request_path(path: str) -> bool:
    normalized = normalize_request_path_for_match(path)
    return normalized == OPENAI_COMPAT_PREFIX or normalized.startswith(
        OPENAI_COMPAT_PREFIX_WITH_SLASH,
    )


def is_openai_api_request_path(path: str) -> bool:
    normalized = normalize_request_path_for_match(path)
    return (
        is_openai_compatibility_request_path(normalized)
        and normalized != OPENAI_COMPAT_PREFIX
        and not is_anthropic_api_request_path(normalized)
    ) or normalized == SOAI_API_OPENAPI_SCHEMA_PATH


def is_anthropic_api_request_path(path: str) -> bool:
    normalized = normalize_request_path_for_match(path)
    return normalized == ANTHROPIC_MESSAGES_PATH or normalized.startswith(
        f"{ANTHROPIC_MESSAGES_PATH}/"
    )


def is_public_inference_api_request_path(path: str) -> bool:
    return is_openai_api_request_path(path) or is_anthropic_api_request_path(path)


def is_mcp_request_path(path: str) -> bool:
    normalized = normalize_request_path_for_match(path)
    return normalized == MCP_ROOT_PATH or normalized.startswith(MCP_API_PREFIX)


def is_wizard_status_endpoint(path: str, method: str) -> bool:
    normalized_path = str(path or "")
    normalized_method = str(method or "").upper()
    return normalized_path == SOAI_WEBUI_WIZARD_STATUS_PATH and normalized_method == "GET"


def is_wizard_bootstrap_endpoint(path: str, method: str) -> bool:
    normalized_path = str(path or "")
    normalized_method = str(method or "").upper()
    if normalized_method == "GET" and normalized_path in {
        SOAI_WEBUI_WIZARD_EVALUATION_TERMS_PATH,
        SOAI_WEBUI_WIZARD_PERSONAL_PURCHASE_TERMS_PATH,
    }:
        return True
    if normalized_method == "GET" and normalized_path.startswith(
        SOAI_WEBUI_WIZARD_GOVERNING_DOCUMENTS_PREFIX,
    ):
        flow = normalized_path.removeprefix(SOAI_WEBUI_WIZARD_GOVERNING_DOCUMENTS_PREFIX)
        return bool(flow) and "/" not in flow
    return normalized_method in {"POST", "PUT"} and normalized_path in {
        SOAI_WEBUI_WIZARD_COMPLETE_PATH,
        "/api/v1/webui/wizard/license/accept",
        "/api/v1/webui/wizard/use",
        "/api/v1/webui/wizard/licensing/evaluation",
        "/api/v1/webui/wizard/licensing/activation",
        "/api/v1/webui/wizard/licensing/operation-reconciliation",
        "/api/v1/webui/wizard/licensing/offline-request",
        "/api/v1/webui/wizard/licensing/offline-import",
    }
