"""SoAI - WebSocket system-events authentication [backend/features/api/routes/system/events/websocket_authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.auth.jwt_tokens import extract_session_jti
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.licensing.access_policy import apply_licensing_action_policy
from core.logging.trace import get_context_trace_id, get_logger
from core.state.access import AccessAction, AccessState
from core.state.access_policy_effective import resolve_effective_actions
from core.state.access_policy_overrides import get_effective_access_policy
from features.api.middleware.acl_enforcement import (
    resolve_access_state,
)
from features.api.runtime.auth_request_state import evaluate_and_apply_request_authentication
from features.api.streaming.websocket import resolve_websocket_close_code

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebSocketRequestAdapter

__all__ = (
    "AuthenticatedWebsocketSession",
    "authenticate_websocket_session",
)

LOGGER_NAME = "SoAI.features.api.websocket_authentication"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_AUTHENTICATE = (
    "api_system.websocket.system_events.authenticate"
)


@dataclass(frozen=True, slots=True)
class AuthenticatedWebsocketSession:
    user: JSONDict
    granted_actions: frozenset[AccessAction]
    trace_id: str | None
    jti: str


async def _resolve_granted_actions(
    request: RequestProtocol,
    api_context: ApiContext,
    auth_method: str,
    explicit_actions: frozenset[AccessAction],
) -> tuple[AccessState, frozenset[AccessAction]]:
    webui_manager = api_context.dependencies.webui_manager
    database_plugins = api_context.dependencies.database_plugins
    access_state = await resolve_access_state(request, webui_manager, database_plugins)
    policy = await get_effective_access_policy(
        api_context.dependencies.access_policy_cache,
        database_plugins,
    )
    allowed_actions = policy.get(access_state, frozenset())
    granted_actions = resolve_effective_actions(
        auth_method=auth_method,
        granted_actions=explicit_actions,
        allowed_actions=allowed_actions,
    )
    licensing_status = await api_context.dependencies.licensing_service.resolved_status()
    granted_actions = apply_licensing_action_policy(granted_actions, licensing_status)
    request.state.licensing_status = licensing_status
    request.state.effective_access_actions = granted_actions
    request.state.context.access_actions = granted_actions
    return (access_state, granted_actions)


async def _close_unauthenticated_websocket(
    websocket: WebSocket,
    *,
    access_state: AccessState,
    status_code: int | None,
    error_message: str | None,
) -> None:
    if access_state == AccessState.UNINITIALIZED:
        await websocket.close(
            code=4001,
            reason="System setup is required. Please complete the initial wizard.",
        )
        return
    close_reason = error_message or "Authentication required"
    websocket_close_code = resolve_websocket_close_code(status_code) if status_code else 4001
    await websocket.close(code=websocket_close_code, reason=close_reason)


async def authenticate_websocket_session(
    websocket: WebSocket,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
) -> AuthenticatedWebsocketSession | None:
    webui_manager = api_context.dependencies.webui_manager
    auth_config = api_context.dependencies.auth_config
    verification_secrets = auth_config.verification_secrets
    if not verification_secrets:
        await websocket.close(code=1011, reason="JWT secret unavailable")
        return None
    try:
        auth_decision = await evaluate_and_apply_request_authentication(
            request,
            webui_manager,
            verification_secrets=verification_secrets,
            algorithm=auth_config.algorithm,
        )
    except RECOVERABLE_EXCEPTIONS as auth_exc:
        log_exception(
            get_logger(LOGGER_NAME),
            auth_exc,
            message="WebSocket authentication failed",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_AUTHENTICATE,
        )
        await websocket.close(code=1011, reason="Authentication failed")
        return None
    context = request_adapter.state.context
    trace_id = get_context_trace_id(context)
    explicit_actions = frozenset(auth_decision.granted_actions or ())
    access_state, granted_actions = await _resolve_granted_actions(
        request,
        api_context,
        auth_decision.auth_method,
        explicit_actions,
    )
    user = auth_decision.user
    if user is None:
        await _close_unauthenticated_websocket(
            websocket,
            access_state=access_state,
            status_code=auth_decision.status_code,
            error_message=auth_decision.error_message,
        )
        return None
    if context is not None:
        context.user_id = user.get("id", 0)
    if AccessAction.AUTH_COOKIE not in granted_actions:
        await websocket.close(code=4003, reason="Session access denied")
        return None
    jti = extract_session_jti(auth_decision.token_payload)
    if jti is None:
        await websocket.close(code=4001, reason="Session identity unavailable")
        return None
    return AuthenticatedWebsocketSession(
        user=user,
        granted_actions=granted_actions,
        trace_id=trace_id,
        jti=jti,
    )
