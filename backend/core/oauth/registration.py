"""SoAI - OAuth client credential resolution helpers [backend/core/oauth/registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.network.http_json import read_http_json_dict
from core.oauth.protocols import OAuthHTTPClientProtocol
from core.oauth.types import (
    OAuthAuthorizationServerMetadata,
    OAuthClientCredentials,
    OAuthError,
    OAuthErrorCode,
)
from core.types.json import JSONValue

if TYPE_CHECKING:
    type ValidateURL = Callable[[str, str], Awaitable[None]]

__all__ = ("resolve_client_credentials",)


async def resolve_client_credentials(
    http_client: OAuthHTTPClientProtocol,
    *,
    auth_server: OAuthAuthorizationServerMetadata,
    redirect_uri: str,
    public_client_metadata_url: str | None,
    preregistered_client_id: str | None,
    preregistered_client_secret: str | None,
    validate_url: ValidateURL,
    timeout_sec: float = 15.0,
) -> OAuthClientCredentials:
    if preregistered_client_id:
        token_method = _pick_token_auth_method(
            auth_server.token_endpoint_auth_methods_supported,
            preferred="client_secret_basic" if preregistered_client_secret else "none",
        )
        if token_method != "none" and not preregistered_client_secret:
            raise OAuthError(
                OAuthErrorCode.MANUAL_CLIENT_REQUIRED,
                "Client secret required for selected token endpoint authentication method.",
            )
        return OAuthClientCredentials(
            client_id=preregistered_client_id,
            client_secret=preregistered_client_secret,
            token_endpoint_auth_method=token_method,
        )
    if auth_server.client_id_metadata_document_supported:
        if public_client_metadata_url:
            _require_https_with_path(public_client_metadata_url, "public_client_metadata_url")
            _require_https_with_path(redirect_uri, "redirect_uri")
            await validate_url(public_client_metadata_url, "OAuth client metadata document URL")
            return OAuthClientCredentials(
                client_id=public_client_metadata_url,
                client_secret=None,
                token_endpoint_auth_method="none",
            )
    if auth_server.registration_endpoint:
        await validate_url(
            auth_server.registration_endpoint,
            "OAuth dynamic client registration endpoint",
        )
        token_method = _pick_registration_token_auth_method(
            auth_server.token_endpoint_auth_methods_supported,
        )
        payload = _build_registration_payload(redirect_uri, token_endpoint_auth_method=token_method)
        response = await http_client.post(
            auth_server.registration_endpoint,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout_sec,
        )
        if response.status_code not in (200, 201):
            raise OAuthError(
                OAuthErrorCode.REGISTRATION_FAILED,
                f"Dynamic client registration failed (HTTP {response.status_code}).",
            )
        try:
            body = read_http_json_dict(
                response,
                field="OAuth dynamic client registration response",
            )
        except ValidationError as exception:
            raise OAuthError(
                OAuthErrorCode.REGISTRATION_FAILED,
                str(exception),
            ) from exception
        client_id = body.get("client_id")
        if not isinstance(client_id, str) or not client_id.strip():
            raise OAuthError(
                OAuthErrorCode.REGISTRATION_FAILED,
                "Dynamic client registration response missing client_id.",
            )
        client_secret_value = body.get("client_secret")
        client_secret = (
            client_secret_value.strip()
            if isinstance(client_secret_value, str) and client_secret_value.strip()
            else None
        )
        method_value = body.get("token_endpoint_auth_method")
        method = method_value if isinstance(method_value, str) and method_value.strip() else None
        token_method = _pick_token_auth_method(
            auth_server.token_endpoint_auth_methods_supported,
            preferred=method or ("client_secret_basic" if client_secret else "none"),
        )
        if token_method != "none" and not client_secret:
            raise OAuthError(
                OAuthErrorCode.REGISTRATION_FAILED,
                "Dynamic client registration did not return client_secret for required auth method.",
            )
        return OAuthClientCredentials(
            client_id=client_id.strip(),
            client_secret=client_secret,
            token_endpoint_auth_method=token_method,
        )
    raise OAuthError(
        OAuthErrorCode.MANUAL_CLIENT_REQUIRED,
        "Authorization server requires a manually configured OAuth client.",
        details={"required_fields": ["client_id", "client_secret?"]},
    )


def _pick_token_auth_method(
    supported: tuple[str, ...] | None,
    *,
    preferred: str,
) -> str:
    if supported is None:
        return preferred
    normalized = {entry.strip().lower() for entry in supported if entry.strip()}
    preferred_normalized = preferred.strip().lower()
    if preferred_normalized in normalized:
        return preferred_normalized
    if "client_secret_basic" in normalized:
        return "client_secret_basic"
    if "client_secret_post" in normalized:
        return "client_secret_post"
    if "none" in normalized:
        return "none"
    return preferred_normalized


def _pick_registration_token_auth_method(
    supported: tuple[str, ...] | None,
) -> str:
    if supported is None:
        return "client_secret_basic"
    normalized = {entry.strip().lower() for entry in supported if entry.strip()}
    for candidate in ("client_secret_basic", "client_secret_post", "none"):
        if candidate in normalized:
            return candidate
    return "client_secret_basic"


def _build_registration_payload(
    redirect_uri: str,
    *,
    token_endpoint_auth_method: str,
) -> Mapping[str, JSONValue]:
    return {
        "client_name": "SoAI MCP Client",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": token_endpoint_auth_method,
    }


def _require_https_with_path(url: str, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValidationError(f"{label} must be https.")
    if not parsed.path or parsed.path == "/":
        raise ValidationError(f"{label} must include a path component.")
