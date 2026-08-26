"""SoAI - OAuth engine dataclasses and error taxonomy [backend/core/oauth/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import override

from core.types.json import JSONDict

__all__ = (
    "OAuthAuthorizationServerMetadata",
    "OAuthChallenge",
    "OAuthClientCredentials",
    "OAuthError",
    "OAuthErrorCode",
    "OAuthFlowState",
    "OAuthProtectedResourceMetadata",
    "OAuthTokens",
)


class OAuthErrorCode(str, Enum):
    DISCOVERY_FAILED = "discovery_failed"
    MANUAL_CLIENT_REQUIRED = "manual_client_required"
    AUTH_REQUIRED = "auth_required"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    INVALID_STATE = "invalid_state"
    TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    REGISTRATION_FAILED = "registration_failed"
    INVALID_METADATA = "invalid_metadata"


@dataclass(frozen=True, slots=True)
class OAuthError(Exception):
    code: OAuthErrorCode
    message: str
    details: JSONDict | None = None

    @override
    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class OAuthChallenge:
    resource_metadata: str | None
    scope: str | None
    error: str | None
    error_description: str | None


@dataclass(frozen=True, slots=True)
class OAuthProtectedResourceMetadata:
    resource: str | None
    authorization_servers: tuple[str, ...]
    scopes_supported: tuple[str, ...] | None
    raw: JSONDict


@dataclass(frozen=True, slots=True)
class OAuthAuthorizationServerMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None
    token_endpoint_auth_methods_supported: tuple[str, ...] | None
    code_challenge_methods_supported: tuple[str, ...] | None
    client_id_metadata_document_supported: bool
    raw: JSONDict


@dataclass(frozen=True, slots=True)
class OAuthClientCredentials:
    client_id: str
    client_secret: str | None
    token_endpoint_auth_method: str


@dataclass(frozen=True, slots=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int | None
    scope: str | None
    token_type: str
    raw: JSONDict


@dataclass(frozen=True, slots=True)
class OAuthFlowState:
    server_id: str
    user_id: int
    code_verifier: str
    resource: str
    redirect_uri: str
    scopes: tuple[str, ...]
    created_at_ms: int
