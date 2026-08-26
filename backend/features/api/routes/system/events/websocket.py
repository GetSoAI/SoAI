"""SoAI - WebSocket endpoint for system events [backend/features/api/routes/system/events/websocket.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import ipaddress
from typing import TYPE_CHECKING, TypeGuard

from fastapi import WebSocket

from core.config.value_validation import is_config_value
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.fastapi_request_context import setup_request_context
from core.system_api.route_paths import SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.types.json import is_json_dict
from features.api.middleware.security.networks import (
    client_ip_allowed,
    is_ip_network_tuple,
)
from features.api.middleware.security.websocket_origins import (
    should_allow_websocket_bootstrap_origin,
    websocket_origin_allowed,
)
from features.api.rate_limiting.rate_limit_evaluator import evaluate_rate_limit
from features.api.rate_limiting.rate_limit_notifications import (
    notify_rate_limit_breach_noncritical,
)
from features.api.routes.system.events.websocket_authentication import (
    authenticate_websocket_session,
)
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)
from features.api.routes.system.events.websocket_permission_rules import (
    build_websocket_event_permission_rules,
)
from features.api.routes.system.events.websocket_runtime import run_websocket_events
from features.api.runtime.app_state_access import require_app_state
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import resolve_api_context
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.websocket import (
    WebsocketConnection,
    WebSocketRequestAdapter,
    resolve_websocket_client_host,
    resolve_websocket_close_code,
)

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict

__all__ = (
    "register_routes",
    "resolve_api_context",
    "websocket_events",
)

LOGGER_NAME = "SoAI.features.api.websocket"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_ACCEPT = "api_system.websocket.system_events.accept"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_RATE_LIMIT = (
    "api_system.websocket.system_events.rate_limit"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_SETUP_REQUEST_CONTEXT = (
    "api_system.websocket.system_events.setup_request_context"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_RESOLVE_CLIENT = (
    "api_system.websocket.system_events.resolve_client"
)


def _is_trusted_origin_tuple(value: ConfigValue | None) -> TypeGuard[tuple[str, ...]]:
    if not isinstance(value, tuple):
        return False
    return all(isinstance(item, str) for item in value)


async def websocket_events(websocket: WebSocket) -> None:
    try:
        client_host = resolve_websocket_client_host(websocket)
        whitelist, blacklist = _resolve_websocket_ip_filters(websocket)
        cors_config, trusted_origins = _resolve_websocket_cors_state(websocket)
    except StateError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to resolve WebSocket runtime state.",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_RESOLVE_CLIENT,
        )
        await websocket.close(code=1011, reason="Internal error")
        return
    if not client_ip_allowed(client_host, whitelist, blacklist):
        await websocket.close(code=4003, reason="IP not allowed")
        return
    request_adapter = WebSocketRequestAdapter(websocket)
    request_adapter.state.client_host = client_host
    request: RequestProtocol = request_adapter
    origin = websocket.headers.get("origin")
    origin_allowed = websocket_origin_allowed(
        origin,
        cors_config,
        trusted_origins,
        websocket.headers.get("host"),
        websocket.url.scheme,
    )
    if not origin_allowed:
        api_context = resolve_api_context(websocket)
        origin_allowed = await should_allow_websocket_bootstrap_origin(
            api_context.dependencies.webui_manager,
        )
    if not origin_allowed:
        await websocket.close(code=4003, reason="Origin not allowed")
        return
    try:
        setup_request_context(request, "ws")
    except RECOVERABLE_EXCEPTIONS as context_error:
        log_exception(
            get_logger(LOGGER_NAME),
            context_error,
            message="Failed to initialize WebSocket request context",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_SETUP_REQUEST_CONTEXT,
        )
        await websocket.close(code=1011, reason="Internal error")
        return
    api_context = resolve_api_context(websocket)
    authenticated_session = await authenticate_websocket_session(
        websocket,
        request,
        request_adapter,
        api_context,
    )
    if authenticated_session is None:
        return
    try:
        breach = await evaluate_rate_limit(
            request,
            SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH,
            SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH,
        )
    except RECOVERABLE_EXCEPTIONS as rate_limit_error:
        log_exception(
            get_logger(LOGGER_NAME),
            rate_limit_error,
            message="WebSocket rate limit evaluation failed.",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_RATE_LIMIT,
        )
        await websocket.close(code=1011, reason="Internal error")
        return
    if breach is not None:
        await notify_rate_limit_breach_noncritical(
            database_notifications=api_context.dependencies.database_notifications,
            breach=breach,
            log=get_logger(LOGGER_NAME),
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_RATE_LIMIT,
        )
        await websocket.close(code=resolve_websocket_close_code(429), reason="Rate limit exceeded")
        return
    try:
        await asyncio.wait_for(websocket.accept(), timeout=CONTROL_TIMEOUT_SEC)
    except TimeoutError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="WebSocket accept timed out.",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_ACCEPT,
            level="warning",
        )
        await websocket.close(code=1011, reason="Accept timeout")
        return
    event_permissions = dict(build_websocket_event_permission_rules())
    connection = WebsocketConnection(
        websocket,
        request,
        api_context,
        authenticated_session.user,
        authenticated_session.granted_actions,
        event_permissions,
        get_logger(LOGGER_NAME),
        authenticated_session.jti,
        authenticated_session.trace_id,
    )
    stream_dependencies = build_stream_dependencies(api_context.dependencies)
    shutdown_event = api_context.dependencies.shutdown_event
    enqueue_warning_tracker = api_context.dependencies.enqueue_warning_tracker
    await run_websocket_events(
        runtime_context=WebsocketEventRuntimeContext(
            websocket=websocket,
            request=request,
            request_adapter=request_adapter,
            api_context=api_context,
            connection=connection,
            stream_dependencies=stream_dependencies,
            shutdown_event=shutdown_event,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=authenticated_session.trace_id,
        ),
    )


def register_routes(routers: ApiRouters) -> None:
    routers.system.websocket("/ws")(websocket_events)


def _resolve_websocket_ip_filters(
    websocket: WebSocket,
) -> tuple[
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
]:
    app_state = require_app_state(websocket)
    try:
        whitelist = app_state.client_ip_whitelist
        blacklist = app_state.client_ip_blacklist
    except AttributeError as exception:
        raise StateError("WebSocket IP filter runtime state is not configured.") from exception
    if not is_ip_network_tuple(whitelist) or not is_ip_network_tuple(blacklist):
        raise StateError("WebSocket IP filter runtime state is not configured.")
    return (whitelist, blacklist)


def _resolve_websocket_cors_state(websocket: WebSocket) -> tuple[JSONDict, tuple[str, ...]]:
    app_state = require_app_state(websocket)
    try:
        cors_config = app_state.cors_config
        trusted_origins = app_state.cors_trusted_origins
    except AttributeError as exception:
        raise StateError("WebSocket CORS runtime state is not configured.") from exception
    if not is_json_dict(cors_config):
        raise StateError("WebSocket CORS runtime state is not configured.")
    if not is_config_value(trusted_origins) or not _is_trusted_origin_tuple(trusted_origins):
        raise StateError("WebSocket CORS runtime state is not configured.")
    return (cors_config, trusted_origins)
