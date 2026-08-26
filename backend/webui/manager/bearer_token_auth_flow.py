"""SoAI - Shared bearer token authentication flow primitives [backend/webui/manager/bearer_token_auth_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import status

from core.auth.api_keys import fingerprint_api_key
from core.auth.auth_decisions import AuthenticationDecision
from core.auth.auth_failure_buckets import build_auth_failure_buckets
from core.auth.auth_guard_throttling import resolve_auth_guard_throttle
from core.auth.hashed_bearer_token_validation import validate_hashed_bearer_token_record
from core.auth.jwt_tokens import extract_bearer_token
from core.errors.exceptions import StateError
from core.runtime.protocols import RequestProtocol
from webui.manager.auth_failure_reporter import AuthFailureReporter
from webui.manager.request_client_ip import resolve_request_client_ip

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.wallpaper.protocols import AuthGuardProtocol

__all__ = (
    "BearerTokenAuthAttempt",
    "prepare_bearer_token_auth_attempt",
    "report_invalid_bearer_record_failure",
    "resolve_bearer_token_id_or_failure",
    "resolve_bearer_token_throttle",
)


@dataclass(frozen=True, slots=True)
class BearerTokenAuthAttempt:
    client_ip: str
    token_value: str | None
    fingerprints: tuple[str, ...]
    bucket_identifiers: tuple[str, ...]

    @property
    def primary_fingerprint(self) -> str | None:
        return self.fingerprints[0] if self.fingerprints else None


def prepare_bearer_token_auth_attempt(
    *,
    request: RequestProtocol,
    ip_bucket_prefix: str,
    token_bucket_prefix: str,
    secret_keys: tuple[str, ...],
    provided_token: str | None = None,
) -> BearerTokenAuthAttempt:
    client_ip = resolve_request_client_ip(request)
    bearer_token = extract_bearer_token(request.headers.get("Authorization"))
    token_value = (
        provided_token if provided_token is not None else bearer_token or ""
    ).strip() or None
    fingerprints = (
        tuple(fingerprint_api_key(token_value, secret_key=secret_key) for secret_key in secret_keys)
        if token_value is not None
        else ()
    )
    return BearerTokenAuthAttempt(
        client_ip=client_ip,
        token_value=token_value,
        fingerprints=fingerprints,
        bucket_identifiers=build_auth_failure_buckets(
            ip_bucket_prefix=ip_bucket_prefix,
            token_bucket_prefix=token_bucket_prefix,
            client_ip=client_ip,
            provided_token=token_value,
            token_fingerprint=fingerprints[0] if fingerprints else None,
        ),
    )


async def resolve_bearer_token_throttle(
    *,
    guard: AuthGuardProtocol,
    attempt: BearerTokenAuthAttempt,
    auth_method: str,
    failure_category: str | None,
    trace_id: str | None,
) -> AuthenticationDecision | None:
    throttled, retry_at = await resolve_auth_guard_throttle(guard, attempt.bucket_identifiers)
    if not throttled:
        return None
    return AuthenticationDecision(
        continue_request=False,
        auth_method=auth_method,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        error_type="authentication_error",
        error_message="Too many authentication failures. Retry later.",
        failure_category=failure_category,
        rate_limit_reset=retry_at,
        trace_id=trace_id,
    )


async def resolve_bearer_token_id_or_failure(
    *,
    record: JSONDict,
    attempt: BearerTokenAuthAttempt,
    failure_reporter: AuthFailureReporter,
    id_field: str,
    salt_field: str,
    hash_field: str,
    secret_keys: tuple[str, ...],
    use_reason_as_failure_category: bool,
) -> str | AuthenticationDecision:
    token_value = attempt.token_value
    if token_value is None:
        raise StateError("Bearer token validation requires a provided token.")
    fingerprint = attempt.primary_fingerprint
    if fingerprint is None:
        raise StateError("Bearer token validation requires a token fingerprint.")
    validation = validate_hashed_bearer_token_record(
        record=record,
        provided_token=token_value,
        id_field=id_field,
        salt_field=salt_field,
        hash_field=hash_field,
        secret_keys=secret_keys,
    )
    if not validation.valid:
        return await failure_reporter.report_failure(
            "You are not authenticated.",
            validation.reason,
            bucket_identifiers=attempt.bucket_identifiers,
            fingerprint=fingerprint[:12],
            failure_category=validation.reason if use_reason_as_failure_category else None,
        )
    token_id = validation.token_id
    if token_id is None:
        return await report_invalid_bearer_record_failure(
            failure_reporter=failure_reporter,
            attempt=attempt,
            fingerprint=fingerprint,
            use_reason_as_failure_category=use_reason_as_failure_category,
        )
    return token_id


async def report_invalid_bearer_record_failure(
    *,
    failure_reporter: AuthFailureReporter,
    attempt: BearerTokenAuthAttempt,
    fingerprint: str,
    use_reason_as_failure_category: bool,
) -> AuthenticationDecision:
    return await failure_reporter.report_failure(
        "You are not authenticated.",
        "invalid_record",
        bucket_identifiers=attempt.bucket_identifiers,
        fingerprint=fingerprint[:12],
        failure_category="invalid_record" if use_reason_as_failure_category else None,
    )
