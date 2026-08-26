"""SoAI - API HTTPS redirect middleware [backend/features/api/middleware/https_redirect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import State
from starlette.types import ASGIApp, Receive, Scope, Send

from core.errors.exceptions import StateError
from core.runtime.proxy_headers import client_is_trusted_proxy, resolve_request_scheme
from core.runtime.state_access import read_state_flag, read_state_has_key, read_state_value

__all__ = ("HTTPSRedirectMiddleware",)


class HTTPSRedirectMiddleware:
    def __init__(self, app: ASGIApp, *, enabled: bool = False) -> None:
        self.app = app
        self._initial_enabled = bool(enabled)

    @staticmethod
    def _state_redirect_enabled(request: Request) -> bool | None:
        app_state = request.app.state
        if not isinstance(app_state, State):
            return None
        force_https_redirect = read_state_value(app_state, "force_https_redirect", bool)
        if force_https_redirect is None:
            return None
        return force_https_redirect

    def _should_redirect(self, request: Request) -> bool:
        if request.scope.get("type") != "http":
            return False
        state_flag = self._state_redirect_enabled(request)
        if state_flag is not None:
            return state_flag
        return self._initial_enabled

    @staticmethod
    def _local_tls_enabled(request: Request) -> bool | None:
        app_state = request.app.state
        if not isinstance(app_state, State):
            return None
        if not read_state_has_key(app_state, "local_tls_enabled"):
            return None
        return read_state_flag(app_state, "local_tls_enabled")

    def _request_supports_redirect_target(self, request: Request) -> bool:
        local_tls_enabled = self._local_tls_enabled(request)
        if local_tls_enabled is None:
            return self._initial_enabled
        if local_tls_enabled:
            return True
        return client_is_trusted_proxy(request)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._should_redirect(request):
            return await call_next(request)
        if not self._request_supports_redirect_target(request):
            return await call_next(request)
        try:
            scheme = resolve_request_scheme(request)
        except StateError:
            return await call_next(request)
        if scheme == "https":
            return await call_next(request)
        target_url = request.url.replace(scheme="https")
        return RedirectResponse(str(target_url), status_code=308)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        if not self._should_redirect(request):
            await self.app(scope, receive, send)
            return
        if not self._request_supports_redirect_target(request):
            await self.app(scope, receive, send)
            return
        try:
            scheme = resolve_request_scheme(request)
        except StateError:
            await self.app(scope, receive, send)
            return
        if scheme == "https":
            await self.app(scope, receive, send)
            return
        target_url = request.url.replace(scheme="https")
        redirect_response = RedirectResponse(str(target_url), status_code=308)
        await redirect_response(scope, receive, send)
