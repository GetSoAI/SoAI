"""SoAI - Request source resolution helpers [backend/core/runtime/request_source_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.meta.soai_v1_contract import SOAI_OPENAI_COMPAT_V1_PREFIX
from core.runtime.protocols import RequestProtocol
from core.runtime.request_sources import (
    REQUEST_SOURCE_OPENAI,
    REQUEST_SOURCE_WEBUI_WS,
    RequestSource,
)
from core.system_api.request_paths import get_scope_path

__all__ = (
    "resolve_request_source_for_auth_method",
    "resolve_request_source_for_request",
)


def _is_openai_compat_path(path: str) -> bool:
    normalized_path = path.rstrip("/") or "/"
    prefix = SOAI_OPENAI_COMPAT_V1_PREFIX.rstrip("/") or SOAI_OPENAI_COMPAT_V1_PREFIX
    return normalized_path == prefix or normalized_path.startswith(f"{prefix}/")


def resolve_request_source_for_auth_method(auth_method: str | None) -> RequestSource:
    normalized = auth_method.strip() if isinstance(auth_method, str) else ""
    if normalized == "openai_api_key":
        return REQUEST_SOURCE_OPENAI
    return REQUEST_SOURCE_WEBUI_WS


def resolve_request_source_for_request(request: RequestProtocol) -> RequestSource:
    path = get_scope_path(request.scope)
    if _is_openai_compat_path(path):
        return REQUEST_SOURCE_OPENAI
    try:
        auth_method = request.state.auth_method
    except AttributeError:
        auth_method = None
    return resolve_request_source_for_auth_method(auth_method)
