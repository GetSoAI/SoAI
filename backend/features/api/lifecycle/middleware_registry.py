"""SoAI - Middleware registration and ordering for FastAPI application [backend/features/api/lifecycle/middleware_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from features.api.api_cors_runtime import CORSMiddlewareConfig
from features.api.middleware.authentication import AuthMiddleware
from features.api.middleware.https_redirect import HTTPSRedirectMiddleware
from features.api.middleware.openai_anonymous_owner_token import OpenAIAnonymousOwnerTokenMiddleware
from features.api.middleware.openai_api_key_quotas import OpenAIAPIKeyQuotaMiddleware
from features.api.middleware.openai_response_metadata import OpenAIResponseMetadataMiddleware
from features.api.middleware.proxy_headers import ProxyHeaderMiddleware, TrustedProxyMiddleware
from features.api.middleware.quiesce import QuiesceMiddleware, ensure_quiesce_drain_state
from features.api.middleware.request_body_guard import RequestBodyGuardMiddleware
from features.api.middleware.restart_notice import RestartNoticeMiddleware
from features.api.middleware.security_headers import SecurityHeadersMiddleware
from features.api.middleware.server_time import ServerTimeMiddleware
from features.api.middleware.startup_gate import StartupGateMiddleware
from features.api.middleware.trusted_origins import TrustedOriginMiddleware
from features.api.request_body_policy import RequestBodyPolicy

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type MiddlewareClass = (
        type[
            RestartNoticeMiddleware
            | RequestBodyGuardMiddleware
            | AuthMiddleware
            | OpenAIAPIKeyQuotaMiddleware
            | HTTPSRedirectMiddleware
            | QuiesceMiddleware
            | StartupGateMiddleware
            | TrustedOriginMiddleware
            | TrustedProxyMiddleware
            | ProxyHeaderMiddleware
            | SecurityHeadersMiddleware
            | ServerTimeMiddleware
            | OpenAIResponseMetadataMiddleware
            | CORSMiddleware
        ]
    )

__all__ = (
    "register_middleware_stack",
    "update_middleware_options",
)


def register_middleware_stack(
    app: FastAPI,
    cors_config: CORSMiddlewareConfig,
    security_headers_state: SecurityHeadersMiddleware.ConfigState | None,
    https_redirect_enabled: bool,
    request_body_policy: RequestBodyPolicy,
) -> None:
    ensure_quiesce_drain_state(app)
    app.add_middleware(RequestBodyGuardMiddleware, policy=request_body_policy)
    app.add_middleware(RestartNoticeMiddleware)
    app.add_middleware(OpenAIAPIKeyQuotaMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware, enabled=https_redirect_enabled)
    app.add_middleware(QuiesceMiddleware)
    app.add_middleware(StartupGateMiddleware)
    app.add_middleware(TrustedOriginMiddleware)
    app.add_middleware(TrustedProxyMiddleware)
    app.add_middleware(ProxyHeaderMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, config_state=security_headers_state)
    app.add_middleware(OpenAIAnonymousOwnerTokenMiddleware)
    app.add_middleware(ServerTimeMiddleware)
    app.add_middleware(OpenAIResponseMetadataMiddleware)
    app.add_middleware(CORSMiddleware, **cors_config)


def update_middleware_options(
    app: FastAPI,
    middleware_cls: MiddlewareClass,
    options: Mapping[str, JSONValue],
) -> bool:
    try:
        middleware_entries = app.user_middleware
    except AttributeError:
        return False
    for middleware_entry in middleware_entries:
        try:
            entry_cls = middleware_entry.cls
        except AttributeError:
            entry_cls = None
        if isinstance(entry_cls, type) and entry_cls is middleware_cls:
            try:
                option_values = middleware_entry.kwargs
            except AttributeError:
                option_values = None
            if not isinstance(option_values, dict):
                return False
            option_values.clear()
            for key, value in options.items():
                option_values[key] = value
            return True
    return False
