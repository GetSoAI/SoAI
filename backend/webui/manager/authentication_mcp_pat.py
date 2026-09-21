"""SoAI - WebUI MCP personal access token authentication logic [backend/webui/manager/authentication_mcp_pat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.auth_decisions import AuthenticationDecision
from core.auth.auth_guard_throttling import (
    reset_auth_guard_failures,
)
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from core.validation.coercion import coerce_int_from_scalar
from core.webui_manager.protocols import WebUIAuthContextProtocol
from webui.manager.auth_failure_reporter import AuthFailureReporter
from webui.manager.auth_inactive_record_failure import (
    report_inactive_record_auth_failure,
)
from webui.manager.bearer_token_auth_flow import (
    prepare_bearer_token_auth_attempt,
    report_bearer_record_failure,
    resolve_bearer_token_id_or_failure,
    resolve_bearer_token_throttle,
    resolve_bearer_user_record_or_failure,
)

__all__ = ("evaluate_mcp_pat_authentication",)

LOGGER_NAME = "SoAI.webui.manager.authentication_mcp_pat"
_MCP_ACTIONS = frozenset({AccessAction.MCP_USE, AccessAction.TERMINAL_USE})


async def evaluate_mcp_pat_authentication(
    *,
    request: RequestProtocol,
    webui_mgr: WebUIAuthContextProtocol | None,
    trace_id: str | None,
    verification_secrets: tuple[str, ...],
) -> AuthenticationDecision:
    logger = get_logger(LOGGER_NAME)
    if webui_mgr is None:
        raise StateError("MCP requests require a WebUI manager instance.")
    token_store = webui_mgr.database_mcp_access_tokens
    database_users = webui_mgr.database_users
    guard = webui_mgr.mcp_pat_auth_guard
    attempt = prepare_bearer_token_auth_attempt(
        request=request,
        ip_bucket_prefix="mcp_pat_auth_ip",
        token_bucket_prefix="mcp_pat_auth",
        secret_keys=verification_secrets,
    )
    failure_reporter = AuthFailureReporter(
        request=request,
        guard=guard,
        log_failure=webui_mgr.log_mcp_pat_auth_failure,
        trace_id=trace_id,
        auth_method="mcp_pat_failure",
        client_ip=attempt.client_ip,
    )

    throttled_decision = await resolve_bearer_token_throttle(
        guard=guard,
        attempt=attempt,
        auth_method="mcp_pat_failure",
        failure_category=None,
        trace_id=trace_id,
    )
    if throttled_decision is not None:
        return throttled_decision
    token_value = attempt.token_value
    if token_value is None:
        return await failure_reporter.report_failure(
            "You are not authenticated.",
            "missing_token",
            bucket_identifiers=attempt.bucket_identifiers,
        )
    fingerprint = attempt.primary_fingerprint
    if fingerprint is None:
        raise StateError("MCP PAT authentication requires a token fingerprint.")
    now_ms = epoch_ms()
    token_record = await token_store.get_active_token_by_fingerprints(
        attempt.fingerprints,
        now_ms=now_ms,
    )
    if token_record is None:
        inactive_record = await token_store.get_token_by_fingerprints(attempt.fingerprints)
        return await report_inactive_record_auth_failure(
            failure_reporter=failure_reporter,
            inactive_record=inactive_record if isinstance(inactive_record, dict) else None,
            fingerprint=fingerprint,
            now_ms=int(now_ms),
            logger=logger,
            coerce_bool_operation="webui.manager.authentication_mcp_pat.coerce_bool_flag",
            bucket_identifiers=attempt.bucket_identifiers,
            use_reason_as_failure_category=False,
        )
    if not isinstance(token_record, dict):
        raise StateError("MCP token store returned an invalid record type.")
    token_id_or_failure = await resolve_bearer_token_id_or_failure(
        record=token_record,
        attempt=attempt,
        failure_reporter=failure_reporter,
        id_field="token_id",
        salt_field="salt",
        hash_field="hashed_token",
        secret_keys=verification_secrets,
        use_reason_as_failure_category=False,
    )
    if isinstance(token_id_or_failure, AuthenticationDecision):
        return token_id_or_failure
    token_id_value = token_id_or_failure
    owner_id = coerce_int_from_scalar(token_record.get("user_id"))
    if owner_id is None:
        return await report_bearer_record_failure(
            failure_reporter=failure_reporter,
            attempt=attempt,
            fingerprint=fingerprint,
            reason="invalid_record",
            use_reason_as_failure_category=False,
        )
    user_record = await database_users.get_human_user_by_id(int(owner_id))
    resolved_user = await resolve_bearer_user_record_or_failure(
        user_record,
        failure_reporter=failure_reporter,
        attempt=attempt,
        use_reason_as_failure_category=False,
    )
    if isinstance(resolved_user, AuthenticationDecision):
        return resolved_user
    await token_store.record_last_used(token_id_value, now_ms=now_ms)
    await reset_auth_guard_failures(guard, attempt.bucket_identifiers)
    payload = {
        "token_id": token_id_value,
        "prefix": token_record.get("prefix"),
        "label": token_record.get("label"),
        "expires_at_ms": token_record.get("expires_at_ms"),
    }
    return AuthenticationDecision(
        continue_request=True,
        auth_method="mcp_pat",
        user=resolved_user,
        token_payload=payload,
        granted_actions=_MCP_ACTIONS,
    )
