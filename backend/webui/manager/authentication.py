"""SoAI - WebUI authentication request evaluation and decision logic [backend/webui/manager/authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import status

from core.auth.auth_decisions import AuthenticationDecision
from core.auth.cookie_authentication import (
    evaluate_optional_jwt_cookie_authentication,
    evaluate_session_rotation_cookie_authentication,
)
from core.auth.cookies import resolve_webui_cookie_names
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import DatabaseError, StateError
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.runtime.proxy_headers import resolve_request_scheme
from core.runtime.request_trace_id import get_request_trace_id
from core.system_api.request_paths import (
    get_scope_path,
    is_mcp_request_path,
    is_public_inference_api_request_path,
    is_wizard_bootstrap_endpoint,
    is_wizard_status_endpoint,
)
from core.users.bootstrap_state import BootstrapState
from core.webui_manager.protocols import WebUIAuthContextProtocol
from webui.manager.authentication_mcp_pat import evaluate_mcp_pat_authentication
from webui.manager.authentication_openai_api import evaluate_openai_api_authentication

__all__ = (
    "evaluate_authentication_request",
    "manager_supports_jwt",
)

LOGGER_NAME = "SoAI.webui.manager.authentication"
OPERATION = "webui.authentication.evaluate_authentication_request"
SESSION_ROTATION_RECOVERY_PATH = "/api/v1/webui/auth/session-rotation/recover"


def manager_supports_jwt(manager: WebUIAuthContextProtocol) -> bool:
    database_users = manager.database_users
    database_tokens = manager.database_tokens
    return database_users is not None and database_tokens is not None


async def evaluate_authentication_request(
    request: RequestProtocol,
    *,
    verification_secrets: tuple[str, ...],
    algorithm: str,
    webui_mgr: WebUIAuthContextProtocol,
) -> AuthenticationDecision:
    logger = get_logger(LOGGER_NAME)
    path = get_scope_path(request.scope)
    method = request.method
    public_inference_api_request = is_public_inference_api_request_path(path)
    trace_id = get_request_trace_id(request)
    try:
        bootstrap_state = await webui_mgr.get_bootstrap_state()
    except (DatabaseError, StateError) as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Failed to determine bootstrap state.",
            trace_id=trace_id,
            operation=OPERATION,
        )
        raise StateError("Failed to determine bootstrap state.", cause=exception) from exception
    if is_wizard_status_endpoint(path, method):
        return AuthenticationDecision(continue_request=True, auth_method="none")
    if bootstrap_state is BootstrapState.UNINITIALIZED:
        if is_wizard_bootstrap_endpoint(path, method):
            return AuthenticationDecision(continue_request=True, auth_method="wizard_bootstrap")
        return AuthenticationDecision(
            continue_request=False,
            auth_method="none",
            status_code=status.HTTP_403_FORBIDDEN,
            error_type="setup_required",
            error_message="System setup is required. Please complete the initial wizard.",
            trace_id=trace_id,
        )
    if is_mcp_request_path(path):
        return await evaluate_mcp_pat_authentication(
            request=request,
            webui_mgr=webui_mgr,
            trace_id=trace_id,
            verification_secrets=verification_secrets,
        )
    if manager_supports_jwt(webui_mgr):
        if not public_inference_api_request:
            decision, invalid_cookie_exception = await evaluate_optional_jwt_cookie_authentication(
                request,
                secret_keys=verification_secrets,
                algorithm=algorithm,
                database_tokens=webui_mgr.database_tokens,
            )
            if decision is not None:
                return decision
            if invalid_cookie_exception is not None:
                log_handled_exception(
                    logger,
                    invalid_cookie_exception,
                    message="Invalid JWT cookie provided (non-critical).",
                    operation=OPERATION,
                    level="debug",
                )
            if path == SESSION_ROTATION_RECOVERY_PATH:
                recovery_decision = await evaluate_session_rotation_cookie_authentication(
                    request,
                    secret_keys=verification_secrets,
                    algorithm=algorithm,
                    database_tokens=webui_mgr.database_tokens,
                )
                if recovery_decision is not None:
                    return recovery_decision
    else:
        cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
        token_candidates = request.cookies.get(cookie_names.auth)
        if token_candidates and (not public_inference_api_request):
            logger.debug(
                "Skipping cookie authentication because WebUI manager does not expose JWT helpers.",
            )
    if is_public_inference_api_request_path(path):
        return await evaluate_openai_api_authentication(
            request=request,
            webui_mgr=webui_mgr,
            trace_id=trace_id,
            verification_secrets=verification_secrets,
        )
    return AuthenticationDecision(
        continue_request=False,
        auth_method="none",
        status_code=status.HTTP_401_UNAUTHORIZED,
        error_type="authentication_error",
        error_message="You are not authenticated.",
        trace_id=trace_id,
    )
