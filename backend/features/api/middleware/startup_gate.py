"""SoAI - API startup gating middleware [backend/features/api/middleware/startup_gate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.config.numeric import coerce_positive_float
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.system_api.request_paths import (
    PublicRequestSurface,
    get_scope_path,
    resolve_public_request_surface,
)
from core.system_api.route_paths import (
    SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH,
    SOAI_SYSTEM_FAST_FAIL_PATHS,
)
from features.api.middleware.websocket_rejection import reject_websocket_connection
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)
from features.api.runtime.context import get_request_trace_id, resolve_api_context

__all__ = ("StartupGateMiddleware",)


class StartupGateMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _resolve_trace_id(request: Request) -> str:
        trace_id = get_request_trace_id(request)
        if trace_id:
            return trace_id
        return create_prefixed_hex_id("startup", length=12)

    @classmethod
    def _build_startup_rejection(
        cls: type[StartupGateMiddleware],
        request: Request,
    ) -> JSONResponse:
        return build_boundary_error_json_response_for_request(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="The server is still starting up.",
            soai_code="server_not_ready",
            openai_code="server_not_ready",
            headers={"Retry-After": "1"},
            trace_id=cls._resolve_trace_id(request),
        )

    @classmethod
    def _build_shutdown_rejection(
        cls: type[StartupGateMiddleware],
        request: Request,
    ) -> JSONResponse:
        return build_boundary_error_json_response_for_request(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="The server is shutting down.",
            soai_code="server_shutting_down",
            openai_code="server_shutting_down",
            headers={"Retry-After": "1"},
            trace_id=cls._resolve_trace_id(request),
        )

    @staticmethod
    async def _reject_websocket_starting(receive: Receive, send: Send) -> None:
        await reject_websocket_connection(
            receive,
            send,
            code=1013,
            reason="The server is still starting up.",
        )

    @staticmethod
    async def _reject_websocket_shutting_down(receive: Receive, send: Send) -> None:
        await reject_websocket_connection(
            receive,
            send,
            code=1012,
            reason="The server is shutting down.",
        )

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = get_scope_path(scope)
        if path != SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH:
            await self.app(scope, receive, send)
            return
        api_context = resolve_api_context(HTTPConnection(scope))
        startup_event = api_context.dependencies.startup_ready_event
        shutdown_event = api_context.dependencies.shutdown_event
        if shutdown_event.is_set():
            await self._reject_websocket_shutting_down(receive, send)
            return
        if startup_event.is_set():
            if shutdown_event.is_set():
                await self._reject_websocket_shutting_down(receive, send)
                return
            await self.app(scope, receive, send)
            return
        await self._reject_websocket_starting(receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type == "http":
            await self._handle_http(scope, receive, send)
            return
        if scope_type == "websocket":
            await self._handle_websocket(scope, receive, send)
            return
        await self.app(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        path = get_scope_path(request.scope)
        public_surface = resolve_public_request_surface(path, request.method)
        if public_surface is PublicRequestSurface.WEBUI:
            await self.app(scope, receive, send)
            return
        api_context = resolve_api_context(request)
        startup_event = api_context.dependencies.startup_ready_event
        shutdown_event = api_context.dependencies.shutdown_event
        if shutdown_event.is_set():
            response = self._build_shutdown_rejection(request)
            await response(scope, receive, send)
            return
        if startup_event.is_set():
            if shutdown_event.is_set():
                response = self._build_shutdown_rejection(request)
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return
        if path in SOAI_SYSTEM_FAST_FAIL_PATHS:
            response = self._build_startup_rejection(request)
            await response(scope, receive, send)
            return
        timeout_default = 0.0
        timeout_value = api_context.dependencies.config.get(
            "MODELS.ROUTING.HEALTH_CHECKS.PENDING_STARTUP_TASK_TIMEOUT_SEC",
            timeout_default,
        )
        timeout_default = coerce_positive_float(
            timeout_value,
            default=timeout_default,
            minimum=0.0,
            maximum=30.0,
        )
        if timeout_default <= 0:
            response = self._build_startup_rejection(request)
            await response(scope, receive, send)
            return
        startup_task = create_ephemeral_task(startup_event.wait(), name="startup-gate-ready")
        shutdown_task = create_ephemeral_task(shutdown_event.wait(), name="startup-gate-shutdown")
        try:
            done, _pending = await asyncio.wait(
                {startup_task, shutdown_task},
                timeout=timeout_default,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in (startup_task, shutdown_task):
                if not task.done():
                    task.cancel()
        if shutdown_task in done:
            response = self._build_shutdown_rejection(request)
            await response(scope, receive, send)
            return
        if startup_task not in done:
            response = self._build_startup_rejection(request)
            await response(scope, receive, send)
            return
        if shutdown_event.is_set():
            response = self._build_shutdown_rejection(request)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
