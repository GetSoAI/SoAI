"""SoAI - API quiesce middleware [backend/features/api/middleware/quiesce.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Request, status
from starlette.applications import Starlette
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from core.errors.exceptions import StateError
from core.system_api.request_paths import get_scope_path
from core.system_api.route_paths import SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH
from features.api.middleware.websocket_rejection import reject_websocket_connection
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)
from features.api.runtime.context import get_request_trace_id, resolve_api_context

__all__ = (
    "QuiesceMiddleware",
    "await_quiesce_request_drain",
    "ensure_quiesce_drain_state",
)


@dataclass(slots=True)
class QuiesceDrainState:
    active_requests: int
    accepting_requests: bool
    active_lock: asyncio.Lock
    drained_event: asyncio.Event


def ensure_quiesce_drain_state(app: Starlette) -> QuiesceDrainState:
    try:
        drain_state = app.state.quiesce_drain_state
    except AttributeError:
        drain_state = QuiesceDrainState(
            active_requests=0,
            accepting_requests=True,
            active_lock=asyncio.Lock(),
            drained_event=asyncio.Event(),
        )
        drain_state.drained_event.set()
        app.state.quiesce_drain_state = drain_state
    if isinstance(drain_state, QuiesceDrainState):
        return drain_state
    raise StateError("API quiesce drain state is invalid.")


async def await_quiesce_request_drain(app: Starlette | None, timeout_sec: float) -> bool:
    if app is None:
        return True
    drain_state = ensure_quiesce_drain_state(app)
    async with drain_state.active_lock:
        drain_state.accepting_requests = False
        if drain_state.active_requests <= 0:
            drain_state.active_requests = 0
            drain_state.drained_event.set()
    if timeout_sec <= 0.0:
        return drain_state.drained_event.is_set()
    try:
        await asyncio.wait_for(drain_state.drained_event.wait(), timeout=timeout_sec)
        return True
    except TimeoutError:
        return False


class QuiesceMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    async def _reject_http_shutdown(
        request: Request,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        trace_id = get_request_trace_id(request)
        response = build_boundary_error_json_response_for_request(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="The server is shutting down and is not accepting new requests.",
            soai_code="service_unavailable",
            openai_code="service_unavailable",
            trace_id=trace_id,
        )
        await response(scope, receive, send)

    async def _enter_request(self, drain_state: QuiesceDrainState) -> bool:
        async with drain_state.active_lock:
            if not drain_state.accepting_requests:
                return False
            drain_state.active_requests += 1
            drain_state.drained_event.clear()
            return True

    async def _exit_request(self, drain_state: QuiesceDrainState) -> None:
        async with drain_state.active_lock:
            drain_state.active_requests -= 1
            if drain_state.active_requests <= 0:
                drain_state.active_requests = 0
                drain_state.drained_event.set()

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        if get_scope_path(scope) != SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH:
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        api_context = resolve_api_context(connection)
        orchestrator_control = api_context.dependencies.orchestrator_control
        if orchestrator_control.is_quiescent():
            await reject_websocket_connection(
                receive,
                send,
                code=1012,
                reason="The server is shutting down.",
            )
            return
        drain_state = ensure_quiesce_drain_state(connection.app)
        entered = await self._enter_request(drain_state)
        if not entered:
            await reject_websocket_connection(
                receive,
                send,
                code=1012,
                reason="The server is shutting down.",
            )
            return
        if orchestrator_control.is_quiescent():
            await self._exit_request(drain_state)
            await reject_websocket_connection(
                receive,
                send,
                code=1012,
                reason="The server is shutting down.",
            )
            return
        try:
            await self.app(scope, receive, send)
        finally:
            await self._exit_request(drain_state)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type == "websocket":
            await self._handle_websocket(scope, receive, send)
            return
        if scope_type != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        api_context = resolve_api_context(request)
        orchestrator_control = api_context.dependencies.orchestrator_control
        if orchestrator_control.is_quiescent():
            await self._reject_http_shutdown(request, scope, receive, send)
            return
        drain_state = ensure_quiesce_drain_state(request.app)
        entered = await self._enter_request(drain_state)
        if not entered or orchestrator_control.is_quiescent():
            if entered:
                await self._exit_request(drain_state)
            await self._reject_http_shutdown(request, scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            await self._exit_request(drain_state)
