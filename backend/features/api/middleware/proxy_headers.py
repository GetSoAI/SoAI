"""SoAI - API proxy header middleware [backend/features/api/middleware/proxy_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.runtime.proxy_headers import client_is_trusted_proxy, extract_real_client_ip
from core.runtime.state_access import read_request_state_value, read_state_flag, read_state_value
from features.api.middleware.security.proxy_anomalies import record_proxy_header_anomaly
from features.api.middleware.security.types import ProxyHeaderAnomalyTracker
from features.api.runtime.app_state_access import require_app_state
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "ProxyHeaderMiddleware",
    "TrustedProxyMiddleware",
)

LOGGER_NAME = "SoAI.features.api.proxy_headers"


class ProxyHeaderMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _prepare_request(request: Request) -> None:
        client_host = read_request_state_value(request, "client_host", str)
        if not client_host:
            request.state.client_host = extract_real_client_ip(request)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        self._prepare_request(request)
        await self.app(scope, receive, send)


class TrustedProxyMiddleware:
    _PROXY_HEADER_KEYS = (
        b"x-forwarded-for",
        b"x-forwarded-host",
        b"x-forwarded-port",
        b"x-forwarded-proto",
        b"x-forwarded-client-cert",
        b"forwarded",
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def _prepare_request(self, request: Request) -> None:
        logger = get_logger(LOGGER_NAME)
        app_state = require_app_state(request)
        proxy_headers_enabled = read_state_flag(app_state, "proxy_headers_enabled")
        if proxy_headers_enabled and client_is_trusted_proxy(request):
            return
        headers: list[tuple[bytes, bytes]] = list(request.scope.get("headers") or ())
        if not headers:
            return
        if not proxy_headers_enabled:
            api_dependencies = read_state_value(
                app_state,
                "api_dependencies",
                ApiDependencies,
            )
            if api_dependencies is None:
                raise StateError("API dependencies are not configured.")
            tracker = api_dependencies.proxy_header_anomaly_tracker
            if not isinstance(tracker, ProxyHeaderAnomalyTracker):
                raise StateError("Proxy header anomaly tracker is not configured.")
            record_proxy_header_anomaly(request, tracker)
        proxy_keys = self._PROXY_HEADER_KEYS
        has_proxy_header = any((key.lower() in proxy_keys for key, _ in headers))
        if has_proxy_header:
            filtered = [(key, value) for key, value in headers if key.lower() not in proxy_keys]
            request.scope["headers"] = filtered
            client_host = resolve_client_host(request)
            reason = "proxy headers disabled"
            if proxy_headers_enabled:
                reason = "client not listed as trusted proxy"
            logger.warning("Removed proxy headers from %s because %s.", client_host, reason)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        self._prepare_request(request)
        await self.app(scope, receive, send)
