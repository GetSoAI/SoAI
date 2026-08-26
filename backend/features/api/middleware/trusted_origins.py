"""SoAI - API trusted origin middleware [backend/features/api/middleware/trusted_origins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, status
from starlette.types import ASGIApp, Receive, Scope, Send

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from features.api.middleware.security.same_origin import origin_matches_request_host
from features.api.middleware.security.websocket_origins import (
    should_allow_websocket_bootstrap_origin,
)
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)
from features.api.runtime.context import get_request_trace_id, resolve_api_context

__all__ = ("TrustedOriginMiddleware",)

LOGGER_NAME = "SoAI.features.api.trusted_origins"


class TrustedOriginMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def _should_allow_bootstrap_origin(self, request: Request) -> bool:
        try:
            state = request.app.state
        except AttributeError:
            state = None
        if state is None:
            raise StateError("API state is not available.")
        api_context = resolve_api_context(request)
        manager = api_context.dependencies.webui_manager
        return await should_allow_websocket_bootstrap_origin(
            manager,
        )

    async def _origin_allowed(self, request: Request, origin: str) -> bool:
        if origin_matches_request_host(origin, request.headers.get("host"), request.url.scheme):
            return True
        try:
            state = request.app.state
        except AttributeError:
            state = None
        if state is None:
            return False
        try:
            trusted_origins_value = state.cors_trusted_origins
        except AttributeError:
            trusted_origins_value = ()
        trusted_origins = tuple(trusted_origins_value or ())
        if trusted_origins and origin in trusted_origins:
            return True
        try:
            origin_regex = state.cors_origin_regex
        except AttributeError:
            origin_regex = None
        if origin_regex is not None and origin_regex.fullmatch(origin):
            return True
        if await self._should_allow_bootstrap_origin(request):
            return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        logger = get_logger(LOGGER_NAME)
        origin = request.headers.get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return
        if await self._origin_allowed(request, origin):
            await self.app(scope, receive, send)
            return
        logger.warning("Blocked request from untrusted origin %s.", origin)
        trace_id = get_request_trace_id(request)
        response = build_boundary_error_json_response_for_request(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            message="Request origin is not allowed.",
            soai_code="origin_not_allowed",
            openai_code="origin_not_allowed",
            trace_id=trace_id,
        )
        await response(scope, receive, send)
