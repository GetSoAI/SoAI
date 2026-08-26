"""SoAI - Request authentication state projection and validation [backend/features/api/runtime/auth_request_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.auth_decisions import AuthenticationDecision
from core.errors.exceptions import SecurityError
from core.runtime.protocols import RequestProtocol
from core.timing.epoch import epoch_ms
from core.webui_manager.protocols import WebUIManagerProtocol

__all__ = (
    "apply_auth_decision_to_request_state",
    "evaluate_and_apply_request_authentication",
    "require_request_auth_method",
)


def apply_auth_decision_to_request_state(
    request: RequestProtocol,
    decision: AuthenticationDecision,
) -> None:
    request.state.auth_method = decision.auth_method
    request.state.user = decision.user
    request.state.token_payload = decision.token_payload
    request.state.granted_actions = decision.granted_actions
    request.state.auth_failure_category = decision.failure_category
    if decision.auth_method in {"jwt_cookie", "jwt_cookie_rotation_recovery"}:
        request.state.authenticated_at_ms = epoch_ms()
    if decision.user:
        user_id_value = decision.user.get("id", 0)
        request.state.context.user_id = user_id_value


async def evaluate_and_apply_request_authentication(
    request: RequestProtocol,
    webui_manager: WebUIManagerProtocol,
    *,
    verification_secrets: tuple[str, ...],
    algorithm: str,
) -> AuthenticationDecision:
    decision = await webui_manager.authenticate_request(
        request,
        verification_secrets=verification_secrets,
        algorithm=algorithm,
    )
    apply_auth_decision_to_request_state(request, decision)
    return decision


def require_request_auth_method(request: RequestProtocol) -> str:
    try:
        auth_method = request.state.auth_method
    except AttributeError as exception:
        raise SecurityError("Request authentication state is unavailable.") from exception
    if not isinstance(auth_method, str):
        raise SecurityError("Request authentication state is invalid.")
    return auth_method
