"""SoAI - OpenAI API key management [backend/core/auth/api_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.auth.auth_decisions import resolve_openai_api_key_action_set
from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.database.requests import InsertAPIKeyRequest
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.base64_values import encode_base64_urlsafe_ascii
from core.timing.durations import days_to_ms
from core.timing.epoch import epoch_ms
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "compute_key_timestamps",
    "create_openai_api_key",
    "fingerprint_api_key",
    "generate_api_key_salt",
    "generate_api_key_secret",
    "hash_api_key",
    "list_openai_api_keys",
    "normalize_api_key_label",
    "normalize_api_key_scopes",
    "revoke_openai_api_key",
    "rotate_openai_api_key",
)

LOGGER_NAME_CORE_WEBUI_TOKENS = "SoAI.core.auth.apikeys"
LOGGER_NAME_CORE_WEBUI_API_TOKENS = "SoAI.core.auth.api_keys"
OPERATION = "core.auth.api_keys.rotate_openai_api_key.parse_revoked"


OPENAI_KEY_ENCRYPTION_VERSION = 1
_SOAI_OPENAI_TOKEN_PREFIX = "soai-"
_SOAI_OPENAI_TOKEN_DERIVATION_NAMESPACE = "soai-api-key-v1"
_SOAI_OPENAI_TOKEN_HMAC_CONTEXT = "soai-bearer-token-storage"


def generate_api_key_secret() -> str:
    encoded_secret = encode_base64_urlsafe_ascii(secrets.token_bytes(32), strip_padding=True)
    return f"{_SOAI_OPENAI_TOKEN_PREFIX}{encoded_secret}"


def generate_api_key_salt() -> str:
    return encode_base64_urlsafe_ascii(secrets.token_bytes(16), strip_padding=True)


def _derive_token_hmac(value: str, *, secret_key: str, purpose: str) -> str:
    secret_text = str(secret_key or "").strip()
    if not secret_text:
        raise ValidationError("Token hash secret key must be configured.")
    payload = f"{_SOAI_OPENAI_TOKEN_DERIVATION_NAMESPACE}:{purpose}:{value}".encode()
    return hmac.new(secret_text.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def fingerprint_api_key(value: str, *, secret_key: str) -> str:
    return _derive_token_hmac(
        value,
        secret_key=secret_key,
        purpose=f"{_SOAI_OPENAI_TOKEN_HMAC_CONTEXT}:fingerprint",
    )


def hash_api_key(value: str, salt: str, *, secret_key: str) -> str:
    return _derive_token_hmac(
        value,
        secret_key=secret_key,
        purpose=f"{_SOAI_OPENAI_TOKEN_HMAC_CONTEXT}:hash:{salt}",
    )


def normalize_api_key_label(label: JSONValue | None) -> str:
    text = str(label or "").strip()
    return text or "Untitled Key"


def normalize_api_key_scopes(scopes: JSONValue | Iterable[str] | None) -> tuple[str, ...]:
    if scopes is None:
        resolved = resolve_openai_api_key_action_set(None)
    elif isinstance(scopes, str):
        resolved = resolve_openai_api_key_action_set((scopes,))
    elif isinstance(scopes, Iterable):
        if isinstance(scopes, dict):
            raise ValidationError("Scopes must be an array of strings.")
        values = tuple(value for value in scopes if isinstance(value, str) and value)
        resolved = resolve_openai_api_key_action_set(values)
    else:
        raise ValidationError("Scopes must be an array of strings.")
    return tuple(action.value for action in resolved)


def compute_key_timestamps(
    *,
    created_at: int,
    expires_in_days: int | None,
    expires_at_ms: int | None,
    rotation_reminder_in_days: int | None,
    default_ttl_days: int,
    default_rotation_days: int,
) -> tuple[int | None, int | None]:
    resolved_expiration = None
    if expires_at_ms:
        resolved_expiration = int(expires_at_ms)
    elif expires_in_days:
        resolved_expiration = created_at + days_to_ms(max(int(expires_in_days), 0))
    elif default_ttl_days > 0:
        resolved_expiration = created_at + days_to_ms(default_ttl_days)
    reminder_days = (
        rotation_reminder_in_days
        if rotation_reminder_in_days is not None
        else default_rotation_days
    )
    resolved_reminder = None
    if reminder_days and int(reminder_days) > 0:
        resolved_reminder = created_at + days_to_ms(int(reminder_days))
    return (resolved_expiration, resolved_reminder)


async def list_openai_api_keys(
    key_store: DatabaseAPIKeysProtocol,
    include_revoked: bool = False,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME_CORE_WEBUI_TOKENS)
    entries = await key_store.list_keys(include_revoked=include_revoked)
    for entry in entries:
        try:
            entry["scopes"] = normalize_api_key_scopes(entry.get("scopes"))
        except ValidationError as exception:
            key_id = entry.get("key_id")
            logger.warning(
                "Invalid stored API key scopes; treating as no scopes (key_id=%s): %s",
                key_id if isinstance(key_id, str) else "unknown",
                str(exception),
            )
            entry["scopes"] = ()
    return entries


async def create_openai_api_key(
    key_store: DatabaseAPIKeysProtocol,
    *,
    label: str | None,
    scopes: Iterable[str] | None,
    created_by: int | None,
    expires_in_days: int | None = None,
    expires_at_ms: int | None = None,
    rotation_reminder_in_days: int | None = None,
    default_ttl_days: int = 0,
    default_rotation_days: int = 0,
    secret_key: str,
) -> JSONDict:
    normalized_label = normalize_api_key_label(label)
    normalized_scopes = normalize_api_key_scopes(scopes)
    secret = generate_api_key_secret()
    salt = generate_api_key_salt()
    created_ts = epoch_ms()
    resolved_expiration, resolved_reminder = compute_key_timestamps(
        created_at=created_ts,
        expires_in_days=expires_in_days,
        expires_at_ms=expires_at_ms,
        rotation_reminder_in_days=rotation_reminder_in_days,
        default_ttl_days=default_ttl_days,
        default_rotation_days=default_rotation_days,
    )
    record = await key_store.insert_key(
        InsertAPIKeyRequest(
            key_id=str(uuid.uuid4()),
            hashed_key=hash_api_key(secret, salt, secret_key=secret_key),
            salt=salt,
            fingerprint=fingerprint_api_key(secret, secret_key=secret_key),
            label=normalized_label,
            prefix=secret[:12],
            scopes=normalized_scopes,
            created_by=created_by,
            expires_at_ms=resolved_expiration,
            rotation_reminder_at_ms=resolved_reminder,
            encryption_version=OPENAI_KEY_ENCRYPTION_VERSION,
            created_at_ms=created_ts,
        ),
    )
    record["scopes"] = normalize_api_key_scopes(record.get("scopes"))
    return {"key": secret, **record}


async def rotate_openai_api_key(
    key_store: DatabaseAPIKeysProtocol,
    key_id: str,
    *,
    label: str | None,
    scopes: Iterable[str] | None,
    created_by: int | None,
    expires_in_days: int | None = None,
    expires_at_ms: int | None = None,
    rotation_reminder_in_days: int | None = None,
    default_ttl_days: int = 0,
    default_rotation_days: int = 0,
    secret_key: str,
) -> JSONDict | None:
    current = await key_store.get_key_by_id(key_id)
    if not current:
        return None
    revoked = False
    try:
        revoked = bool(parse_bool(current.get("revoked"), default=False))
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME_CORE_WEBUI_API_TOKENS),
            exception,
            message="Failed to parse revoked flag for API key rotation (non-critical).",
            operation=OPERATION,
            details={"key_id": str(key_id)},
            level="debug",
        )
        revoked = False
    if revoked:
        return None
    next_label = normalize_api_key_label(label or current.get("label"))
    next_scopes = normalize_api_key_scopes(scopes or current.get("scopes"))
    created = await create_openai_api_key(
        key_store,
        label=next_label,
        scopes=next_scopes,
        created_by=created_by,
        expires_in_days=expires_in_days,
        expires_at_ms=expires_at_ms,
        rotation_reminder_in_days=rotation_reminder_in_days,
        default_ttl_days=default_ttl_days,
        default_rotation_days=default_rotation_days,
        secret_key=secret_key,
    )
    await revoke_openai_api_key(key_store, key_id, created_by)
    return created


async def revoke_openai_api_key(
    key_store: DatabaseAPIKeysProtocol,
    key_id: str,
    revoked_by: int | None,
) -> JSONDict | None:
    record = await key_store.revoke_key(key_id, revoked_by)
    if record:
        record["scopes"] = normalize_api_key_scopes(record.get("scopes"))
    return record
