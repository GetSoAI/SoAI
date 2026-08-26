"""SoAI - MCP personal access token helpers [backend/core/auth/mcp_access_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.auth.api_keys import (
    fingerprint_api_key,
    generate_api_key_salt,
    generate_api_key_secret,
    hash_api_key,
)
from core.auth.protocols_database_mcp_access_tokens import (
    DatabaseMcpAccessTokensProtocol,
)
from core.database.requests import InsertMcpAccessTokenRequest
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MCP_ACCESS_TOKEN_ENCRYPTION_VERSION",
    "create_mcp_access_token",
    "list_mcp_access_tokens",
    "normalize_mcp_access_token_expires_at",
    "normalize_mcp_access_token_label",
    "revoke_mcp_access_token",
)

MCP_ACCESS_TOKEN_ENCRYPTION_VERSION = 1


def _sanitize_mcp_access_token_metadata(record: JSONDict) -> JSONDict:
    allowed_keys = (
        "token_id",
        "prefix",
        "label",
        "created_at_ms",
        "last_used_at_ms",
        "expires_at_ms",
        "revoked",
        "revoked_at_ms",
    )
    return {key: record.get(key) for key in allowed_keys}


def normalize_mcp_access_token_label(value: str | None) -> str:
    text = str(value or "").strip()
    return text or "Untitled Token"


def normalize_mcp_access_token_expires_at(expires_at_ms: int | None, *, now_ms: int) -> int | None:
    if expires_at_ms is None:
        return None
    resolved = int(expires_at_ms)
    if resolved <= int(now_ms):
        raise ValidationError("Expiration timestamp must be in the future.")
    return resolved


async def create_mcp_access_token(
    token_store: DatabaseMcpAccessTokensProtocol,
    *,
    user_id: int,
    label: str | None,
    expires_at_ms: int | None,
    secret_key: str,
) -> JSONDict:
    created_at_ms = epoch_ms()
    secret = generate_api_key_secret()
    salt = generate_api_key_salt()
    fingerprint = fingerprint_api_key(secret, secret_key=secret_key)
    normalized_label = normalize_mcp_access_token_label(label)
    resolved_expires_at_ms = normalize_mcp_access_token_expires_at(
        expires_at_ms,
        now_ms=created_at_ms,
    )
    record = await token_store.insert_token(
        InsertMcpAccessTokenRequest(
            token_id=str(uuid.uuid4()),
            user_id=int(user_id),
            hashed_token=hash_api_key(secret, salt, secret_key=secret_key),
            salt=salt,
            fingerprint=fingerprint,
            label=normalized_label,
            prefix=secret[:12],
            created_at_ms=created_at_ms,
            expires_at_ms=resolved_expires_at_ms,
            encryption_version=MCP_ACCESS_TOKEN_ENCRYPTION_VERSION,
        ),
    )
    return {"token": secret, "metadata": _sanitize_mcp_access_token_metadata(dict(record))}


async def list_mcp_access_tokens(
    token_store: DatabaseMcpAccessTokensProtocol,
    *,
    user_id: int,
    include_revoked: bool,
) -> list[JSONDict]:
    records = await token_store.list_tokens_for_user(int(user_id), include_revoked=include_revoked)
    return [_sanitize_mcp_access_token_metadata(dict(record)) for record in records]


async def revoke_mcp_access_token(
    token_store: DatabaseMcpAccessTokensProtocol,
    token_id: str,
    *,
    revoked_by: int | None,
) -> JSONDict | None:
    record = await token_store.revoke_token(token_id, revoked_by=revoked_by, now_ms=epoch_ms())
    if record is None:
        return None
    return _sanitize_mcp_access_token_metadata(dict(record))
