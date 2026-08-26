"""SoAI - WebUI JWT token operations [backend/core/auth/jwt_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.auth.jwt_claims import decode_signed_webui_token
from core.auth.protocols_database_tokens import (
    DatabaseTokensProtocol,
    SessionLineageRevocationResult,
)
from core.errors.exceptions import SecurityError, StateError
from core.timing.durations import seconds_to_ms
from core.timing.epoch import epoch_ms
from core.types.json import is_json_dict
from core.users.identity_mutation_contract import SESSION_LINEAGE_PRUNE_GRACE_MS
from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict

__all__ = (
    "extract_bearer_token",
    "extract_session_jti",
    "get_user_from_token",
    "invalidate_current_token",
    "require_request_session_expiry_ms",
    "require_request_session_jti",
)


async def get_user_from_token(
    token: str,
    *,
    secret_keys: tuple[str, ...],
    algorithm: str,
    database_tokens: DatabaseTokensProtocol,
) -> tuple[JSONDict, JSONDict]:
    claims = decode_signed_webui_token(
        token,
        secret_keys=secret_keys,
        algorithm=algorithm,
    )
    token_auth_state = await database_tokens.read_token_auth_state(
        jti=claims.jti,
        user_id=claims.user_id,
        username=claims.username,
    )
    if token_auth_state.status != "active":
        raise SecurityError("Authentication token has been revoked.")
    user = token_auth_state.user
    if not user:
        raise SecurityError("Authentication token is invalid.")
    password_revision = user.get("password_revision")
    if not is_strict_int(password_revision):
        raise SecurityError("Authentication token is invalid.")
    if claims.password_revision != int(password_revision):
        raise SecurityError("Authentication token has been invalidated.")
    password_changed_at = user.get("password_changed_at", 0)
    if not isinstance(password_changed_at, int | float):
        raise SecurityError("Authentication token is invalid.")
    if claims.issued_at_ms < int(password_changed_at):
        raise SecurityError("Authentication token has been invalidated.")
    user.pop("hashed_password", None)
    await database_tokens.touch_session(jti=claims.jti, observed_at_ms=epoch_ms())
    return (user, claims.payload)


async def invalidate_current_token(
    request: Request,
    database_tokens: DatabaseTokensProtocol,
) -> SessionLineageRevocationResult | None:
    try:
        token_payload_candidate = request.state.token_payload
    except AttributeError:
        token_payload_candidate = None
    try:
        user_candidate = request.state.user
    except AttributeError:
        user_candidate = None
    token_payload = token_payload_candidate if is_json_dict(token_payload_candidate) else None
    user = user_candidate if is_json_dict(user_candidate) else None
    jti = extract_session_jti(token_payload)
    if jti is not None and user is not None:
        user_id = user.get("id")
        if is_strict_int(user_id):
            try:
                admitted_at_candidate = request.state.authenticated_at_ms
            except AttributeError:
                admitted_at_candidate = None
            admitted_at_ms = (
                int(admitted_at_candidate) if is_strict_int(admitted_at_candidate) else epoch_ms()
            )
            return await database_tokens.revoke_session_lineage(
                user_id=int(user_id),
                source_jti=jti,
                admitted_at_ms=admitted_at_ms,
                deadline_monotonic=(time.monotonic() + SESSION_LINEAGE_PRUNE_GRACE_MS / 1000),
            )
    return None


def extract_session_jti(token_payload: JSONDict | None) -> str | None:
    jti = token_payload.get("jti") if token_payload is not None else None
    return jti if isinstance(jti, str) and jti else None


def require_request_session_jti(request: Request) -> str:
    try:
        token_payload_candidate = request.state.token_payload
    except AttributeError as exception:
        raise StateError("Authenticated session identity is unavailable.") from exception
    token_payload = token_payload_candidate if is_json_dict(token_payload_candidate) else None
    jti = extract_session_jti(token_payload)
    if jti is None:
        raise StateError("Authenticated session identity is unavailable.")
    return jti


def require_request_session_expiry_ms(request: Request) -> int:
    try:
        token_payload_candidate = request.state.token_payload
    except AttributeError as exception:
        raise StateError("Authenticated session expiry is unavailable.") from exception
    token_payload = token_payload_candidate if is_json_dict(token_payload_candidate) else None
    expires_at_seconds = token_payload.get("exp") if token_payload is not None else None
    if not is_strict_int(expires_at_seconds):
        raise StateError("Authenticated session expiry is unavailable.")
    expires_at_ms = seconds_to_ms(int(expires_at_seconds))
    if not is_unix_epoch_ms(expires_at_ms):
        raise StateError("Authenticated session expiry is invalid.")
    return expires_at_ms


def extract_bearer_token(header_value: str | None) -> str:
    if not header_value:
        return ""
    segments = header_value.strip().split()
    if len(segments) != 2:
        return ""
    scheme, token = segments
    if scheme.lower() != "bearer":
        return ""
    return token.strip()
