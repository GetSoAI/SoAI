"""SoAI - WebUI OpenAI API key authentication logic [backend/webui/manager/authentication_openai_api.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status

from core.auth.anthropic_api_tokens import extract_anthropic_api_token
from core.auth.auth_decisions import (
    AuthenticationDecision,
    resolve_openai_api_key_action_set,
)
from core.auth.auth_guard_throttling import (
    reset_auth_guard_failures,
)
from core.auth.openai_protection import OpenAIProtectionState
from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError, StateError, ValidationError
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.state.access import AccessAction
from core.system_api.request_paths import is_anthropic_api_request_path
from core.timing.epoch import epoch_ms
from core.users.user_id import is_strict_user_id
from core.validation.record_fields import require_bool
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

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict, JSONValue

__all__ = ("evaluate_openai_api_authentication",)

LOGGER_NAME = "SoAI.webui.manager.authentication_openai_api"
OPERATION_VALIDATE_ACTIVE_KEY = "webui.authentication_openai_api.validate_active_key"
_OPENAI_ANONYMOUS_ACTIONS = frozenset({AccessAction.OPENAI_API})


def _validate_active_key_record(
    record: JSONValue,
    *,
    logger: TraceLogger,
    trace_id: str | None,
) -> tuple[JSONDict, bool]:
    try:
        if not isinstance(record, dict):
            raise ValidationError("Active OpenAI API key record must be an object.")
        rotation_due = require_bool(
            record.get("rotation_due"),
            label="Active OpenAI API key rotation_due",
            build_error=ValidationError,
        )
    except ValidationError as exception:
        database_error = DatabaseError(
            "OpenAI API key store returned malformed active-key data.",
            operation=OPERATION_VALIDATE_ACTIVE_KEY,
            cause=exception,
            trace_id=trace_id,
        )
        log_exception(
            logger,
            database_error,
            message="OpenAI API key record integrity validation failed.",
            trace_id=trace_id,
            operation=OPERATION_VALIDATE_ACTIVE_KEY,
            details={"record_is_object": isinstance(record, dict), "field": "rotation_due"},
        )
        raise database_error from exception
    return record, rotation_due


async def evaluate_openai_api_authentication(
    *,
    request: RequestProtocol,
    webui_mgr: WebUIAuthContextProtocol | None,
    trace_id: str | None,
    verification_secrets: tuple[str, ...],
) -> AuthenticationDecision:
    logger = get_logger(LOGGER_NAME)
    if webui_mgr is None:
        raise StateError("OpenAI API requests require a WebUI manager instance.")
    key_store = webui_mgr.database_api_keys
    path = request.url.path
    provided_token = (
        extract_anthropic_api_token(request) if is_anthropic_api_request_path(path) else None
    )
    if key_store is None:
        return AuthenticationDecision(
            continue_request=True,
            auth_method="none",
            granted_actions=_OPENAI_ANONYMOUS_ACTIONS,
        )
    protection_state = key_store.protection_state
    if protection_state is OpenAIProtectionState.OPEN:
        return AuthenticationDecision(
            continue_request=True,
            auth_method="none",
            granted_actions=_OPENAI_ANONYMOUS_ACTIONS,
        )
    if protection_state is OpenAIProtectionState.INDETERMINATE:
        return AuthenticationDecision(
            continue_request=False,
            auth_method="openai_api_key_failure",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="service_unavailable",
            error_message="OpenAI API authentication is temporarily unavailable.",
            failure_category="protection_state_indeterminate",
            trace_id=trace_id,
        )
    guard = webui_mgr.openai_auth_guard
    attempt = prepare_bearer_token_auth_attempt(
        request=request,
        ip_bucket_prefix="openai_auth_ip",
        token_bucket_prefix="openai_auth",
        secret_keys=verification_secrets,
        provided_token=provided_token,
    )
    failure_reporter = AuthFailureReporter(
        request=request,
        guard=guard,
        log_failure=webui_mgr.log_openai_auth_failure,
        trace_id=trace_id,
        auth_method="openai_api_key_failure",
        client_ip=attempt.client_ip,
    )
    throttled_decision = await resolve_bearer_token_throttle(
        guard=guard,
        attempt=attempt,
        auth_method="openai_api_key_failure",
        failure_category="rate_limited",
        trace_id=trace_id,
    )
    if throttled_decision is not None:
        return throttled_decision
    if attempt.token_value is None:
        return await failure_reporter.report_failure(
            "You are not authenticated.",
            "missing_token",
            bucket_identifiers=attempt.bucket_identifiers,
            failure_category="missing_token",
        )
    fingerprint = attempt.primary_fingerprint
    if fingerprint is None:
        raise StateError("OpenAI API authentication requires a token fingerprint.")
    key_record = await key_store.get_active_key_by_fingerprints(attempt.fingerprints)
    if key_record is None:
        inactive_record = await key_store.get_key_by_fingerprints(attempt.fingerprints)
        return await report_inactive_record_auth_failure(
            failure_reporter=failure_reporter,
            inactive_record=inactive_record if isinstance(inactive_record, dict) else None,
            fingerprint=fingerprint,
            now_ms=int(epoch_ms()),
            logger=logger,
            coerce_bool_operation="webui.manager.authentication.coerce_bool_flag",
            bucket_identifiers=attempt.bucket_identifiers,
            use_reason_as_failure_category=True,
        )
    key_record, rotation_due = _validate_active_key_record(
        key_record,
        logger=logger,
        trace_id=trace_id,
    )
    key_id_or_failure = await resolve_bearer_token_id_or_failure(
        record=key_record,
        attempt=attempt,
        failure_reporter=failure_reporter,
        id_field="key_id",
        salt_field="salt",
        hash_field="hashed_key",
        secret_keys=verification_secrets,
        use_reason_as_failure_category=True,
    )
    if isinstance(key_id_or_failure, AuthenticationDecision):
        return key_id_or_failure
    key_id = key_id_or_failure
    scopes_raw = key_record.get("scopes")
    try:
        scopes: tuple[str, ...] | None
        if isinstance(scopes_raw, str):
            scopes = (scopes_raw,)
        elif isinstance(scopes_raw, list | tuple | set | frozenset):
            scope_values: list[str] = []
            for scope_value in scopes_raw:
                if not isinstance(scope_value, str):
                    raise ValidationError("Stored API key scopes must contain only strings.")
                scope_values.append(scope_value)
            scopes = tuple(scope_values)
        elif scopes_raw is None:
            scopes = None
        else:
            raise ValidationError("Stored API key scopes must be an array of strings or null.")
        actions = resolve_openai_api_key_action_set(scopes)
    except ValidationError as exception:
        logger.warning(
            "Invalid stored API key scopes (key_id=%s): %s",
            key_id,
            str(exception),
        )
        return await failure_reporter.report_failure(
            "You are not authenticated.",
            "invalid_scopes",
            bucket_identifiers=attempt.bucket_identifiers,
            fingerprint=fingerprint[:12],
            failure_category="invalid_scopes",
        )
    assigned_user_id_value = key_record.get("assigned_user_id")
    if assigned_user_id_value is not None and not is_strict_user_id(assigned_user_id_value):
        return await report_bearer_record_failure(
            failure_reporter=failure_reporter,
            attempt=attempt,
            fingerprint=fingerprint,
            reason="invalid_record",
            use_reason_as_failure_category=True,
        )
    assigned_user_id = assigned_user_id_value if isinstance(assigned_user_id_value, int) else None
    resolved_user = None
    if assigned_user_id is not None:
        database_users = webui_mgr.database_users
        user_record = (
            await database_users.get_human_user_by_id(assigned_user_id)
            if database_users is not None
            else None
        )
        resolved_user_or_failure = await resolve_bearer_user_record_or_failure(
            user_record,
            failure_reporter=failure_reporter,
            attempt=attempt,
            use_reason_as_failure_category=True,
        )
        if isinstance(resolved_user_or_failure, AuthenticationDecision):
            return resolved_user_or_failure
        resolved_user = resolved_user_or_failure
    await reset_auth_guard_failures(guard, attempt.bucket_identifiers)
    payload = {
        "key_id": key_id,
        "label": key_record.get("label"),
        "scopes": [action.value for action in actions],
        "expires_at_ms": key_record.get("expires_at_ms"),
        "rotation_due": rotation_due,
        "request_count": key_record.get("request_count"),
    }
    if resolved_user is not None:
        payload["assigned_user_id"] = assigned_user_id
    return AuthenticationDecision(
        continue_request=True,
        auth_method="openai_api_key",
        user=resolved_user,
        token_payload=payload,
        granted_actions=actions,
    )
