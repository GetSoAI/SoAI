"""SoAI - Signed WebUI JWT claim issuance and validation [backend/core/auth/jwt_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import jwt
from jwt.exceptions import PyJWTError

from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.timing.datetime_conversion import datetime_to_epoch_ms
from core.timing.durations import seconds_to_ms
from core.timing.formatting import utc_now
from core.types.json import is_json_dict
from core.users.user_id import is_strict_user_id
from core.users.username import require_canonical_username
from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AccessTokenRecord",
    "JWT_ALGORITHM",
    "VerifiedWebuiTokenClaims",
    "create_access_token_record",
    "create_exact_access_token_record",
    "decode_signed_webui_token",
)

JWT_ALGORITHM = "HS256"


def _is_valid_jti(value: str) -> bool:
    return bool(value) and value == value.strip() and len(value) <= 128


def _is_valid_token_window(issued_at_ms: int, expires_at_ms: int) -> bool:
    if not is_unix_epoch_ms(issued_at_ms):
        return False
    if not is_unix_epoch_ms(expires_at_ms):
        return False
    return expires_at_ms > issued_at_ms


@dataclass(frozen=True, slots=True)
class AccessTokenRecord:
    token: str
    jti: str
    issued_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class VerifiedWebuiTokenClaims:
    payload: JSONDict
    user_id: int
    username: str
    password_revision: int
    jti: str
    issued_at_ms: int
    expires_at_ms: int


def create_access_token_record(
    secret_key: str,
    data: Mapping[str, JSONValue],
    *,
    expires_delta_minutes: int,
    algorithm: str = JWT_ALGORITHM,
) -> AccessTokenRecord:
    if not secret_key:
        raise StateError("JWT secret key is not configured.")
    to_encode = dict(data)
    now = utc_now()
    expire = now + timedelta(minutes=expires_delta_minutes)
    issued_at_ms = datetime_to_epoch_ms(now)
    jti = uuid.uuid4().hex
    expires_at_seconds = int(expire.timestamp())
    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "iat_ms": issued_at_ms,
            "exp": expires_at_seconds,
            "jti": jti,
        },
    )
    return AccessTokenRecord(
        token=jwt.encode(to_encode, secret_key, algorithm=algorithm),
        jti=jti,
        issued_at_ms=issued_at_ms,
        expires_at_ms=seconds_to_ms(expires_at_seconds),
    )


def create_exact_access_token_record(
    secret_key: str,
    data: Mapping[str, JSONValue],
    *,
    jti: str,
    issued_at_ms: int,
    expires_at_ms: int,
    algorithm: str = JWT_ALGORITHM,
) -> AccessTokenRecord:
    if not secret_key:
        raise StateError("JWT secret key is not configured.")
    if not _is_valid_jti(jti) or not _is_valid_token_window(issued_at_ms, expires_at_ms):
        raise StateError("Stored authentication token metadata is invalid.")
    payload = dict(data)
    payload.update(
        {
            "iat": issued_at_ms // 1000,
            "iat_ms": issued_at_ms,
            "exp": expires_at_ms // 1000,
            "jti": jti,
        },
    )
    return AccessTokenRecord(
        token=jwt.encode(payload, secret_key, algorithm=algorithm),
        jti=jti,
        issued_at_ms=issued_at_ms,
        expires_at_ms=expires_at_ms,
    )


def decode_signed_webui_token(
    token: str,
    *,
    secret_keys: tuple[str, ...],
    algorithm: str,
) -> VerifiedWebuiTokenClaims:
    decoded_payload: JSONDict | None = None
    last_exception: PyJWTError | None = None
    for secret_key in secret_keys:
        try:
            candidate_payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        except PyJWTError as exception:
            last_exception = exception
            continue
        if not is_json_dict(candidate_payload):
            raise SecurityError("Invalid authentication token.")
        decoded_payload = candidate_payload
        break
    if decoded_payload is None:
        if last_exception is not None:
            raise SecurityError("Invalid authentication token.") from last_exception
        raise SecurityError("Invalid authentication token.")
    jti = decoded_payload.get("jti")
    username = decoded_payload.get("sub")
    user_id = decoded_payload.get("uid")
    password_revision = decoded_payload.get("pwd_rev")
    issued_at_ms = decoded_payload.get("iat_ms")
    issued_at_seconds = decoded_payload.get("iat")
    expires_at_seconds = decoded_payload.get("exp")
    try:
        canonical_username = (
            require_canonical_username(username) if isinstance(username, str) else None
        )
    except ValidationError as exception:
        raise SecurityError("Authentication token is invalid.") from exception
    if not isinstance(jti, str) or not _is_valid_jti(jti):
        raise SecurityError("Authentication token is invalid.")
    if canonical_username is None or username != canonical_username:
        raise SecurityError("Authentication token is invalid.")
    if not is_strict_user_id(user_id) or not is_strict_int(password_revision):
        raise SecurityError("Authentication token is invalid.")
    if not 1 <= int(password_revision) <= JAVASCRIPT_SAFE_INTEGER_MAX:
        raise SecurityError("Authentication token is invalid.")
    if not is_strict_int(issued_at_seconds) or not is_strict_int(issued_at_ms):
        raise SecurityError("Authentication token is invalid.")
    if not is_strict_int(expires_at_seconds):
        raise SecurityError("Authentication token is invalid.")
    exact_issued_at_ms = int(issued_at_ms)
    exact_expires_at_ms = seconds_to_ms(int(expires_at_seconds))
    if not _is_valid_token_window(exact_issued_at_ms, exact_expires_at_ms):
        raise SecurityError("Authentication token is invalid.")
    if exact_issued_at_ms // 1000 != int(issued_at_seconds):
        raise SecurityError("Authentication token is invalid.")
    return VerifiedWebuiTokenClaims(
        payload=decoded_payload,
        user_id=int(user_id),
        username=canonical_username,
        password_revision=int(password_revision),
        jti=jti,
        issued_at_ms=exact_issued_at_ms,
        expires_at_ms=exact_expires_at_ms,
    )
