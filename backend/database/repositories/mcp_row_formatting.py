"""SoAI - MCP server row formatting helpers [backend/database/repositories/mcp_row_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.server_config_fields import coerce_row_bool
from core.security.response_redaction import redact_response_payload
from database.core.json_codec import safe_json_deserialize
from database.repositories.row_formatting import format_api_key_field, format_row

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("format_mcp_server_row",)


def format_mcp_server_row(
    row: SQLiteRowDict | None,
    fernet: tuple[Fernet, ...],
    decrypt_key: bool = False,
) -> JSONDict | None:
    if row is None:
        return None
    formatted = format_row(row)
    if formatted is None:
        return None
    if decrypt_key:
        format_api_key_field(
            formatted,
            fernet,
            encrypted_column="api_key_encrypted",
            output_key="api_key",
            decrypt_key=True,
        )
    else:
        format_api_key_field(
            formatted,
            fernet,
            encrypted_column="api_key_encrypted",
            output_key="api_key_masked",
            decrypt_key=False,
        )
        formatted.pop("api_key_encrypted", None)
    formatted["args"] = safe_json_deserialize(row.get("args"), None)
    formatted["env"] = safe_json_deserialize(row.get("env"), None)
    formatted["headers"] = safe_json_deserialize(row.get("headers"), None)
    formatted["oauth_scopes"] = safe_json_deserialize(row.get("oauth_scopes"), None)
    formatted["oauth_required_scopes"] = safe_json_deserialize(
        row.get("oauth_required_scopes"),
        None,
    )
    formatted["capabilities"] = safe_json_deserialize(row.get("capabilities"), None)
    formatted["auto_reconnect"] = coerce_row_bool(formatted.get("auto_reconnect"), default=True)
    formatted["enabled"] = coerce_row_bool(formatted.get("enabled"), default=True)
    if not decrypt_key:
        formatted["args"] = redact_response_payload(formatted.get("args"))
        formatted["env"] = redact_response_payload(formatted.get("env"))
        formatted["headers"] = redact_response_payload(formatted.get("headers"))
        formatted["oauth_has_client_secret"] = bool(formatted.get("oauth_client_secret_encrypted"))
        formatted["oauth_has_access_token"] = bool(formatted.get("oauth_access_token_encrypted"))
        formatted["oauth_has_refresh_token"] = bool(formatted.get("oauth_refresh_token_encrypted"))
        formatted.pop("oauth_client_secret_encrypted", None)
        formatted.pop("oauth_access_token_encrypted", None)
        formatted.pop("oauth_refresh_token_encrypted", None)
    return formatted
