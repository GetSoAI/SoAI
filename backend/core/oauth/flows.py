"""SoAI - OAuth authorization code flows [backend/core/oauth/flows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlparse, urlunparse

from core.errors.exceptions import ValidationError
from core.network.http_json import read_http_json_value
from core.oauth.pkce import code_challenge_s256
from core.oauth.protocols import OAuthHTTPClientProtocol, OAuthHTTPResponseProtocol
from core.oauth.types import (
    OAuthAuthorizationServerMetadata,
    OAuthClientCredentials,
    OAuthError,
    OAuthErrorCode,
    OAuthTokens,
)
from core.serialization.base64_values import encode_base64_ascii
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    type ValidateURL = Callable[[str, str], Awaitable[None]]

__all__ = (
    "build_authorization_url",
    "exchange_authorization_code_for_tokens",
    "oauth_token_expires_within_skew",
    "refresh_access_token",
)


def build_authorization_url(
    *,
    auth_server: OAuthAuthorizationServerMetadata,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_verifier: str,
    resource: str,
    scopes: tuple[str, ...],
) -> str:
    if not auth_server.authorization_endpoint:
        raise ValidationError("authorization_endpoint is required.")
    supported = auth_server.code_challenge_methods_supported
    if supported is not None:
        normalized = {entry.strip().upper() for entry in supported if entry.strip()}
        if "S256" not in normalized:
            raise OAuthError(
                OAuthErrorCode.INVALID_METADATA,
                "Authorization server does not support S256 PKCE.",
            )
    if not state:
        raise ValidationError("OAuth state is required.")
    if not resource:
        raise ValidationError("OAuth resource is required.")
    query: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge_s256(code_verifier),
        "code_challenge_method": "S256",
        "resource": resource,
    }
    if scopes:
        query["scope"] = " ".join(scopes)
    endpoint = auth_server.authorization_endpoint
    parsed = urlparse(endpoint)
    merged_query = _merge_query(parsed.query, query)
    return urlunparse(parsed._replace(query=merged_query))


def oauth_token_expires_within_skew(
    expires_at_ms: int | None,
    *,
    now_ms: int,
    skew_ms: int,
) -> bool:
    if expires_at_ms is None:
        return False
    return expires_at_ms <= (now_ms + max(0, skew_ms))


async def exchange_authorization_code_for_tokens(
    http_client: OAuthHTTPClientProtocol,
    *,
    auth_server: OAuthAuthorizationServerMetadata,
    client: OAuthClientCredentials,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    resource: str,
    validate_url: ValidateURL,
    timeout_sec: float = 20.0,
    now_ms: Callable[[], int],
) -> OAuthTokens:
    if not code:
        raise ValidationError("OAuth authorization code is required.")
    await validate_url(auth_server.token_endpoint, "OAuth token endpoint")
    form: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "resource": resource,
    }
    headers = _build_token_request_headers(client, form)
    response = await http_client.post(
        auth_server.token_endpoint,
        headers=headers,
        data=form,
        timeout=timeout_sec,
    )
    return _parse_token_response(
        response.status_code,
        _read_token_response_payload(
            response,
            failure_code=OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
        ),
        now_ms=now_ms,
        failure_code=OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
    )


async def refresh_access_token(
    http_client: OAuthHTTPClientProtocol,
    *,
    auth_server: OAuthAuthorizationServerMetadata,
    client: OAuthClientCredentials,
    refresh_token: str,
    resource: str,
    validate_url: ValidateURL,
    timeout_sec: float = 20.0,
    now_ms: Callable[[], int],
) -> OAuthTokens:
    if not refresh_token:
        raise ValidationError("OAuth refresh_token is required.")
    await validate_url(auth_server.token_endpoint, "OAuth token endpoint")
    form: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "resource": resource,
    }
    headers = _build_token_request_headers(client, form)
    response = await http_client.post(
        auth_server.token_endpoint,
        headers=headers,
        data=form,
        timeout=timeout_sec,
    )
    return _parse_token_response(
        response.status_code,
        _read_token_response_payload(
            response,
            failure_code=OAuthErrorCode.TOKEN_REFRESH_FAILED,
        ),
        now_ms=now_ms,
        failure_code=OAuthErrorCode.TOKEN_REFRESH_FAILED,
    )


def _build_token_request_headers(
    client: OAuthClientCredentials,
    form: dict[str, str],
) -> Mapping[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    method = client.token_endpoint_auth_method
    if method == "none":
        form["client_id"] = client.client_id
        return headers
    if method == "client_secret_basic":
        if not client.client_secret:
            raise OAuthError(
                OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
                "client_secret is required for client_secret_basic.",
            )
        token = f"{client.client_id}:{client.client_secret}".encode()
        headers["Authorization"] = f"Basic {encode_base64_ascii(token)}"
        return headers
    if method == "client_secret_post":
        if not client.client_secret:
            raise OAuthError(
                OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
                "client_secret is required for client_secret_post.",
            )
        form["client_id"] = client.client_id
        form["client_secret"] = client.client_secret
        return headers
    raise OAuthError(
        OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
        f"Unsupported token_endpoint_auth_method: {method}",
    )


def _read_token_response_payload(
    response: OAuthHTTPResponseProtocol,
    *,
    failure_code: OAuthErrorCode,
) -> JSONValue:
    try:
        return read_http_json_value(response, field="OAuth token response")
    except ValidationError as exception:
        raise OAuthError(failure_code, str(exception)) from exception


def _parse_token_response(
    status_code: int,
    payload: JSONValue,
    *,
    now_ms: Callable[[], int],
    failure_code: OAuthErrorCode,
) -> OAuthTokens:
    if status_code != 200:
        details: JSONDict | None = None
        if isinstance(payload, dict):
            error_value = payload.get("error")
            description_value = payload.get("error_description")
            if isinstance(error_value, str) and error_value.strip():
                details = {"error": error_value.strip()}
                if isinstance(description_value, str) and description_value.strip():
                    details["error_description"] = description_value.strip()
        raise OAuthError(
            failure_code,
            f"Token endpoint returned HTTP {status_code}.",
            details=details,
        )
    if not isinstance(payload, dict):
        raise OAuthError(failure_code, "Token endpoint returned non-object JSON.")
    access_token = payload.get("access_token")
    token_type = payload.get("token_type")
    if not isinstance(access_token, str) or not access_token.strip():
        raise OAuthError(failure_code, "Token response missing access_token.")
    if not isinstance(token_type, str) or not token_type.strip():
        raise OAuthError(failure_code, "Token response missing token_type.")
    if token_type.strip().lower() != "bearer":
        raise OAuthError(failure_code, "Token response token_type must be Bearer.")
    refresh_token_value = payload.get("refresh_token")
    refresh_token = (
        refresh_token_value.strip()
        if isinstance(refresh_token_value, str) and refresh_token_value.strip()
        else None
    )
    scope_value = payload.get("scope")
    scope = scope_value.strip() if isinstance(scope_value, str) and scope_value.strip() else None
    expires_at_ms = _compute_expires_at_ms(payload.get("expires_in"), now_ms=now_ms)
    return OAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at_ms=expires_at_ms,
        scope=scope,
        token_type=token_type.strip(),
        raw=_coerce_json_dict(payload),
    )


def _compute_expires_at_ms(value: JSONValue, *, now_ms: Callable[[], int]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        expires_in = int(float(value))
    except (TypeError, ValueError):
        return None
    if expires_in <= 0:
        return None
    return now_ms() + (expires_in * 1000)


def _coerce_json_dict(payload: Mapping[str, JSONValue]) -> JSONDict:
    out: JSONDict = {}
    for key, value in payload.items():
        if isinstance(key, str):
            out[key] = value
    return out


def _merge_query(existing_query: str, additional: Mapping[str, str]) -> str:
    if not existing_query:
        return urlencode(additional, doseq=True)
    return f"{existing_query}&{urlencode(additional, doseq=True)}"
