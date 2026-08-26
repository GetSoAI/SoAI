"""SoAI - API authentication middleware [backend/features/api/middleware/authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from fastapi import Request, Response, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.auth.cookie_authentication import evaluate_optional_jwt_cookie_authentication
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ApiError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.fastapi_request_context import setup_request_context
from core.system_api.request_paths import (
    PublicRequestSurface,
    get_scope_path,
    is_public_inference_api_request_path,
    resolve_public_request_surface,
)
from core.types.json import is_json_dict
from features.api.middleware.authentication_rate_limits import log_rate_limit_warning
from features.api.middleware.security.csrf import (
    build_csrf_block_response,
    build_csrf_cookie_send_wrapper,
)
from features.api.middleware.security.fetch_metadata import (
    should_block_cross_site_cookie_request,
)
from features.api.middleware.security.networks import client_ip_allowed
from features.api.middleware.security.secure_transport import enforce_secure_transport
from features.api.runtime.auth_request_state import (
    apply_auth_decision_to_request_state,
    evaluate_and_apply_request_authentication,
)
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
    build_boundary_error_json_response_for_soai_error,
)
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.context import (
    get_request_trace_id,
    log_api_exception,
    resolve_api_context,
)
from features.api.runtime.errors import raise_service_unavailable

__all__ = ("AuthMiddleware",)

LOGGER_NAME = "SoAI.features.api.authentication"
OPERATION = "api_middleware.authentication.record_auth_failure_metric"
FETCH_METADATA_BLOCK_MESSAGE = "Cross-site browser request was blocked."


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def _call_next_and_capture_status(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> int:
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_value = message.get("status")
                if isinstance(status_value, int):
                    status_code = status_value
            await send(message)

        await self.app(scope, receive, send_wrapper)
        return status_code

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        logger = get_logger(LOGGER_NAME)
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        path = get_scope_path(request.scope)
        public_surface = resolve_public_request_surface(path, request.method)
        start_time = time.monotonic()
        final_status = 500
        client_host = resolve_client_host(request)
        trace_id_override: str | None = None
        try:
            try:
                start_time = setup_request_context(request, "api")
            except RECOVERABLE_EXCEPTIONS as exception:
                trace_id_override = log_api_exception(
                    logger,
                    request,
                    exception,
                    message="Failed to initialize request context.",
                    operation="api_middleware.setup_request_context",
                    level="error",
                )
                raise ApiError(
                    "The request context could not be established.",
                    code="context_initialization_failed",
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    trace_id=trace_id_override,
                    cause=exception,
                ) from exception
            request.state.client_host = client_host
            try:
                request_context = request.state.context
            except AttributeError as exception:
                raise StateError(
                    "The request context is not available after initialization.",
                    operation="api_middleware.authentication.request_context",
                    cause=exception,
                ) from exception
            request_context.client_ip = client_host
            state = request.app.state
            whitelist = state.client_ip_whitelist
            blacklist = state.client_ip_blacklist
            if not client_ip_allowed(client_host, whitelist, blacklist):
                trace_id = get_request_trace_id(request)
                forbidden_response = build_boundary_error_json_response_for_request(
                    request,
                    status_code=status.HTTP_403_FORBIDDEN,
                    message="Requests from this IP are not allowed.",
                    soai_code="ip_not_allowed",
                    openai_code="ip_not_allowed",
                    trace_id=trace_id,
                )
                final_status = forbidden_response.status_code
                await forbidden_response(scope, receive, send)
                return
            secure_enforcement = enforce_secure_transport(request)
            if secure_enforcement is not None:
                final_status = secure_enforcement.status_code
                await secure_enforcement(scope, receive, send)
                return
            if public_surface is PublicRequestSurface.WEBUI:
                final_status = await self._call_next_and_capture_status(scope, receive, send)
                return
            api_context = resolve_api_context(request)
            if public_surface is PublicRequestSurface.API:
                webui_manager = api_context.dependencies.webui_manager
                auth_config = api_context.dependencies.auth_config
                primary_signing_secret = auth_config.primary_signing_secret
                verification_secrets = auth_config.verification_secrets
                if primary_signing_secret is not None and verification_secrets:
                    try:
                        database_users = webui_manager.database_users
                        database_tokens = webui_manager.database_tokens
                    except AttributeError:
                        database_users = None
                        database_tokens = None
                    if database_users is not None and database_tokens is not None:
                        decision, _invalid_cookie = (
                            await evaluate_optional_jwt_cookie_authentication(
                                request,
                                secret_keys=verification_secrets,
                                algorithm=auth_config.algorithm,
                                database_tokens=database_tokens,
                            )
                        )
                        if decision is not None:
                            apply_auth_decision_to_request_state(request, decision)
                            security_response = self._build_cookie_security_response(
                                request,
                                verification_secrets,
                            )
                            if security_response is not None:
                                final_status = security_response.status_code
                                await security_response(scope, receive, send)
                                return
                            send = build_csrf_cookie_send_wrapper(
                                send,
                                request,
                                api_context.dependencies.config,
                                primary_signing_secret,
                                verification_secrets,
                            )
                final_status = await self._call_next_and_capture_status(scope, receive, send)
                return
            webui_manager = api_context.dependencies.webui_manager
            auth_config = api_context.dependencies.auth_config
            primary_signing_secret = auth_config.primary_signing_secret
            verification_secrets = auth_config.verification_secrets
            if primary_signing_secret is None or not verification_secrets:
                raise_service_unavailable(request, "Authentication secret key is not configured.")
            try:
                auth_decision = await evaluate_and_apply_request_authentication(
                    request,
                    webui_manager,
                    verification_secrets=verification_secrets,
                    algorithm=auth_config.algorithm,
                )
            except ApiError as exception:
                authentication_error_response = build_boundary_error_json_response_for_soai_error(
                    request,
                    exception,
                    trace_id=get_request_trace_id(request),
                )
                final_status = authentication_error_response.status_code
                await authentication_error_response(scope, receive, send)
                return
            response = auth_decision.to_response_for_path(path)
            if response is not None:
                if is_public_inference_api_request_path(path) and auth_decision.failure_category:
                    try:
                        api_context.dependencies.metrics_manager.increment_counter(
                            "api",
                            "openai",
                            "auth_failures",
                            auth_decision.failure_category,
                        )
                    except RECOVERABLE_EXCEPTIONS as exception:
                        log_handled_exception(
                            logger,
                            exception,
                            message="Failed to record OpenAI auth failure metric (non-critical).",
                            operation=OPERATION,
                            details={"failure_category": auth_decision.failure_category},
                            level="debug",
                        )
                final_status = response.status_code
                await response(scope, receive, send)
                return
            security_response = self._build_cookie_security_response(
                request,
                verification_secrets,
            )
            if security_response is not None:
                final_status = security_response.status_code
                await security_response(scope, receive, send)
                return
            send = build_csrf_cookie_send_wrapper(
                send,
                request,
                api_context.dependencies.config,
                primary_signing_secret,
                verification_secrets,
            )
            final_status = await self._call_next_and_capture_status(scope, receive, send)
        finally:
            trace_id = trace_id_override or get_request_trace_id(request) or "unknown"
            try:
                auth_method_value = request.state.auth_method
            except AttributeError:
                auth_method_value = None
            auth_method_text = str(auth_method_value or "unknown")
            try:
                user_value = request.state.user
            except AttributeError:
                user_value = None
            user_json = user_value if is_json_dict(user_value) else None
            username_value = user_json.get("username") if user_json is not None else None
            username_text = username_value if isinstance(username_value, str) else "anonymous"
            elapsed_ms = (time.monotonic() - start_time) * 1000
            log_rate_limit_warning(request, client_host, path, request.method, final_status)
            logger.trace(
                '[%s] API: %s - "%s %s" %s (%.2fms) Auth: %s User: %s',
                trace_id,
                client_host,
                request.method,
                path,
                final_status,
                elapsed_ms,
                auth_method_text,
                username_text,
            )

    def _build_cookie_security_response(
        self,
        request: Request,
        verification_secrets: tuple[str, ...],
    ) -> Response | None:
        fetch_metadata_response = self._build_fetch_metadata_response(request)
        if fetch_metadata_response is not None:
            return fetch_metadata_response
        return build_csrf_block_response(request, verification_secrets)

    def _build_fetch_metadata_response(self, request: Request) -> Response | None:
        try:
            auth_method_value = request.state.auth_method
        except AttributeError:
            auth_method_value = None
        auth_method = auth_method_value if isinstance(auth_method_value, str) else None
        if not should_block_cross_site_cookie_request(request, auth_method):
            return None
        trace_id = get_request_trace_id(request)
        return build_boundary_error_json_response_for_request(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            message=FETCH_METADATA_BLOCK_MESSAGE,
            soai_code="fetch_metadata_cross_site_blocked",
            openai_code="fetch_metadata_cross_site_blocked",
            trace_id=trace_id,
        )
