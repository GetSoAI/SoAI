"""SoAI - OAuth encrypted flow state tokens [backend/core/oauth/state_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from core.errors.exceptions import ValidationError
from core.oauth.management_urls import require_https_url
from core.oauth.types import OAuthError, OAuthErrorCode, OAuthFlowState
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.system_api.route_paths import MCP_OAUTH_CALLBACK_PATH
from core.types.json import JSONValue
from core.validation.integers import (
    is_non_negative_strict_int,
    is_positive_strict_int,
    is_strict_int,
)

__all__ = (
    "OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT",
    "OAUTH_STATE_TOKEN_TYPE_MCP_SERVER",
    "decode_oauth_flow_state",
    "decode_wrapped_oauth_flow_state",
    "encode_oauth_flow_state",
    "encode_wrapped_oauth_flow_state",
    "unwrap_oauth_flow_state_token",
    "wrap_oauth_flow_state_token",
)

OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT = "external_account"
OAUTH_STATE_TOKEN_TYPE_MCP_SERVER = "mcp_server"


def encode_oauth_flow_state(
    fernets: Sequence[Fernet],
    *,
    state: OAuthFlowState,
) -> str:
    if not fernets:
        raise ValidationError("Fernet keys are required for OAuth state token encoding.")
    payload = serialize_json_compact_stable(asdict(state)).encode("utf-8")
    return fernets[0].encrypt(payload).decode("utf-8")


def wrap_oauth_flow_state_token(token: str, *, token_type: str) -> str:
    normalized_type = _require_token_type(token_type)
    normalized_token = _require_inner_token(token)
    return f"{normalized_type}:{normalized_token}"


def encode_wrapped_oauth_flow_state(
    fernets: Sequence[Fernet],
    *,
    state: OAuthFlowState,
    token_type: str,
) -> str:
    return wrap_oauth_flow_state_token(
        encode_oauth_flow_state(fernets, state=state),
        token_type=token_type,
    )


def unwrap_oauth_flow_state_token(
    token: str,
    *,
    expected_token_type: str | None = None,
) -> tuple[str, str]:
    normalized_token = _require_wrapped_token(token)
    wrapped_token_type, separator, inner_token = normalized_token.partition(":")
    if separator != ":":
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Invalid OAuth state token wrapper.")
    normalized_inner_token = inner_token.strip()
    if not normalized_inner_token:
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Invalid OAuth state token wrapper.")
    try:
        normalized_token_type = _require_token_type(wrapped_token_type)
    except ValidationError as exception:
        raise OAuthError(
            OAuthErrorCode.INVALID_STATE,
            "Unsupported OAuth state token type.",
        ) from exception
    if expected_token_type is not None:
        required_token_type = _require_token_type(expected_token_type)
        if normalized_token_type != required_token_type:
            raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state token type mismatch.")
    return normalized_token_type, normalized_inner_token


def decode_oauth_flow_state(
    fernets: Sequence[Fernet],
    *,
    token: str,
    ttl_ms: int,
    now_ms: int,
) -> OAuthFlowState:
    if not fernets:
        raise ValidationError("Fernet keys are required for OAuth state token decoding.")
    if not isinstance(token, str) or not token.strip():
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Missing OAuth state token.")
    if not is_strict_int(now_ms):
        raise ValidationError("now_ms must be an integer.")
    if ttl_ms <= 0:
        raise ValidationError("ttl_ms must be positive.")
    decrypted = _decrypt(fernets, token)
    if decrypted is None:
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Invalid OAuth state token.")
    try:
        raw = parse_json_value(decrypted)
    except (TypeError, ValueError) as exception:
        raise OAuthError(
            OAuthErrorCode.INVALID_STATE,
            "Invalid OAuth state token payload.",
        ) from exception
    if not isinstance(raw, dict):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Invalid OAuth state token payload.")
    flow_state = _parse_flow_state(raw)
    age_ms = now_ms - flow_state.created_at_ms
    if age_ms < 0 or age_ms > ttl_ms:
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state token expired.")
    return flow_state


def decode_wrapped_oauth_flow_state(
    fernets: Sequence[Fernet],
    *,
    token: str,
    expected_token_type: str,
    ttl_ms: int,
    now_ms: int,
) -> OAuthFlowState:
    _, encoded_state_token = unwrap_oauth_flow_state_token(
        token,
        expected_token_type=expected_token_type,
    )
    return decode_oauth_flow_state(
        fernets,
        token=encoded_state_token,
        ttl_ms=ttl_ms,
        now_ms=now_ms,
    )


def _require_token_type(token_type: str) -> str:
    normalized_token_type = token_type.strip() if isinstance(token_type, str) else ""
    if normalized_token_type in {
        OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
        OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
    }:
        return normalized_token_type
    raise ValidationError("OAuth state token type is invalid.")


def _require_inner_token(token: str) -> str:
    normalized_token = token.strip() if isinstance(token, str) else ""
    if not normalized_token:
        raise ValidationError("OAuth state token is invalid.")
    if ":" in normalized_token:
        raise ValidationError("OAuth state token is invalid.")
    return normalized_token


def _require_wrapped_token(token: str) -> str:
    normalized_token = token.strip() if isinstance(token, str) else ""
    if not normalized_token:
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "Missing OAuth state token.")
    return normalized_token


def _decrypt(fernets: Sequence[Fernet], token: str) -> str | None:
    for fernet in fernets:
        try:
            return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except (InvalidToken, TypeError, ValueError):
            continue
    return None


def _parse_flow_state(payload: dict[str, JSONValue]) -> OAuthFlowState:
    server_id = payload.get("server_id")
    user_id = payload.get("user_id")
    code_verifier = payload.get("code_verifier")
    resource = payload.get("resource")
    redirect_uri = payload.get("redirect_uri")
    scopes = payload.get("scopes")
    created_at_ms = payload.get("created_at_ms")
    if not isinstance(server_id, str) or not server_id.strip():
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state missing server_id.")
    if not is_non_negative_strict_int(user_id):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state missing user_id.")
    if not isinstance(code_verifier, str) or not code_verifier.strip():
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state missing code_verifier.")
    if not isinstance(resource, str) or not resource.strip():
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state missing resource.")
    if not isinstance(redirect_uri, str) or not redirect_uri.strip():
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state missing redirect_uri.")
    normalized_redirect_uri = redirect_uri.strip()
    try:
        require_https_url(normalized_redirect_uri, "OAuth state redirect_uri")
    except ValidationError as exception:
        raise OAuthError(
            OAuthErrorCode.INVALID_STATE,
            "OAuth state redirect_uri invalid.",
        ) from exception
    parsed_redirect_uri = urlparse(normalized_redirect_uri)
    if (
        parsed_redirect_uri.path != MCP_OAUTH_CALLBACK_PATH
        or parsed_redirect_uri.params
        or parsed_redirect_uri.query
        or parsed_redirect_uri.fragment
    ):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state redirect_uri invalid.")
    if not isinstance(scopes, list) or any(
        not isinstance(scope_value, str) or not scope_value.strip() for scope_value in scopes
    ):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state scopes invalid.")
    if not is_positive_strict_int(created_at_ms):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state created_at_ms invalid.")
    return OAuthFlowState(
        server_id=server_id.strip(),
        user_id=user_id,
        code_verifier=code_verifier.strip(),
        resource=resource,
        redirect_uri=normalized_redirect_uri,
        scopes=tuple(
            scope_value.strip()
            for scope_value in scopes
            if isinstance(scope_value, str) and scope_value.strip()
        ),
        created_at_ms=created_at_ms,
    )
