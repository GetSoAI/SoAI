"""SoAI - Optional JWT cookie authentication helper [backend/core/auth/cookie_authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.auth_decisions import AuthenticationDecision
from core.auth.cookies import resolve_webui_cookie_names
from core.auth.jwt_claims import decode_signed_webui_token
from core.auth.jwt_tokens import get_user_from_token
from core.auth.protocols_database_tokens import DatabaseTokensProtocol
from core.errors.exceptions import SecurityError, SoAIError
from core.runtime.protocols import RequestProtocol
from core.runtime.proxy_headers import resolve_request_scheme
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms

__all__ = (
    "evaluate_optional_jwt_cookie_authentication",
    "evaluate_session_rotation_cookie_authentication",
    "resolve_cookie_token_candidates",
)


def _parse_cookie_header_values(raw_cookie_header: str, cookie_name: str) -> list[str]:
    parsed_values: list[str] = []
    for cookie_segment in raw_cookie_header.split(";"):
        cookie_key, separator, cookie_value = cookie_segment.partition("=")
        if separator != "=":
            continue
        if cookie_key.strip() != cookie_name:
            continue
        normalized_value = cookie_value.strip()
        if not normalized_value:
            continue
        parsed_values.append(normalized_value)
    return parsed_values


def resolve_cookie_token_candidates(
    request: RequestProtocol,
    *,
    cookie_name: str,
) -> tuple[str, ...]:
    candidates: list[str] = []
    direct_cookie_value = request.cookies.get(cookie_name)
    if isinstance(direct_cookie_value, str):
        normalized_direct_value = direct_cookie_value.strip()
        if normalized_direct_value:
            candidates.append(normalized_direct_value)
    raw_cookie_header = request.headers.get("cookie", "")
    if isinstance(raw_cookie_header, str) and raw_cookie_header:
        for parsed_value in _parse_cookie_header_values(raw_cookie_header, cookie_name):
            if parsed_value not in candidates:
                candidates.append(parsed_value)
    return tuple(candidates)


async def evaluate_optional_jwt_cookie_authentication(
    request: RequestProtocol,
    *,
    secret_keys: tuple[str, ...],
    algorithm: str,
    database_tokens: DatabaseTokensProtocol,
) -> tuple[AuthenticationDecision | None, SoAIError | None]:
    cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
    token_candidates = resolve_cookie_token_candidates(request, cookie_name=cookie_names.auth)
    if not token_candidates:
        return (None, None)
    if len(token_candidates) != 1:
        return (None, SecurityError("Multiple distinct authentication cookies are invalid."))
    last_exception: SoAIError | None = None
    candidate_token = token_candidates[0]
    try:
        user, token_payload = await get_user_from_token(
            candidate_token,
            secret_keys=secret_keys,
            algorithm=algorithm,
            database_tokens=database_tokens,
        )
    except SoAIError as exception:
        last_exception = exception
    else:
        return (
            AuthenticationDecision(
                continue_request=True,
                auth_method="jwt_cookie",
                user=user,
                token_payload=token_payload,
            ),
            None,
        )
    return (None, last_exception)


async def evaluate_session_rotation_cookie_authentication(
    request: RequestProtocol,
    *,
    secret_keys: tuple[str, ...],
    algorithm: str,
    database_tokens: DatabaseTokensProtocol,
) -> AuthenticationDecision | None:
    cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
    token_candidates = resolve_cookie_token_candidates(request, cookie_name=cookie_names.auth)
    if len(token_candidates) != 1:
        return None
    try:
        claims = decode_signed_webui_token(
            token_candidates[0],
            secret_keys=secret_keys,
            algorithm=algorithm,
        )
        recovery = await database_tokens.recover_session_rotation(
            source_jti=claims.jti,
            user_id=claims.user_id,
            source_password_revision=claims.password_revision,
            source_issued_at_ms=claims.issued_at_ms,
            source_expires_at_ms=claims.expires_at_ms,
            observed_at_ms=epoch_ms(),
        )
    except SoAIError:
        return None
    if recovery.status != "recovered" or recovery.user is None:
        return None
    principal = dict(recovery.user)
    principal.pop("hashed_password", None)
    return AuthenticationDecision(
        continue_request=True,
        auth_method="jwt_cookie_rotation_recovery",
        user=principal,
        token_payload=claims.payload,
        granted_actions=frozenset({AccessAction.AUTH_COOKIE}),
    )
