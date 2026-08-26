"""SoAI - OAuth metadata discovery helpers [backend/core/oauth/discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse, urlunparse

from core.errors.exceptions import ValidationError
from core.network.http_json import read_http_json_dict
from core.oauth.protocols import OAuthHTTPClientProtocol
from core.oauth.types import (
    OAuthAuthorizationServerMetadata,
    OAuthChallenge,
    OAuthError,
    OAuthErrorCode,
    OAuthProtectedResourceMetadata,
)
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    type ValidateURL = Callable[[str, str], Awaitable[None]]

__all__ = (
    "discover_authorization_server_metadata",
    "discover_protected_resource_metadata",
)


async def discover_protected_resource_metadata(
    http_client: OAuthHTTPClientProtocol,
    *,
    resource: str,
    challenge: OAuthChallenge | None,
    validate_url: ValidateURL,
    timeout_sec: float = 15.0,
) -> tuple[OAuthProtectedResourceMetadata, str]:
    if not isinstance(resource, str) or not resource.strip():
        raise ValidationError("OAuth protected resource 'resource' is required.")
    if challenge and challenge.resource_metadata:
        url = challenge.resource_metadata
        await validate_url(url, "OAuth protected resource metadata (challenge)")
        metadata = await _fetch_json_dict(http_client, url, timeout_sec=timeout_sec)
        return (_parse_protected_resource_metadata(metadata), url)
    for url in _build_protected_resource_well_known_urls(resource):
        await validate_url(url, "OAuth protected resource metadata (well-known)")
        try:
            metadata = await _fetch_json_dict(http_client, url, timeout_sec=timeout_sec)
        except OAuthError:
            continue
        return (_parse_protected_resource_metadata(metadata), url)
    raise OAuthError(
        OAuthErrorCode.DISCOVERY_FAILED,
        "Protected resource metadata discovery failed.",
        details={"resource": resource},
    )


async def discover_authorization_server_metadata(
    http_client: OAuthHTTPClientProtocol,
    *,
    issuer: str,
    validate_url: ValidateURL,
    timeout_sec: float = 15.0,
) -> OAuthAuthorizationServerMetadata:
    if not isinstance(issuer, str) or not issuer.strip():
        raise ValidationError("OAuth authorization server 'issuer' is required.")
    urls = _build_authorization_server_metadata_urls(issuer)
    last_error: OAuthError | None = None
    for url in urls:
        await validate_url(url, "OAuth authorization server metadata (well-known)")
        try:
            metadata = await _fetch_json_dict(http_client, url, timeout_sec=timeout_sec)
        except OAuthError as exception:
            last_error = exception
            continue
        try:
            return _parse_authorization_server_metadata(metadata)
        except OAuthError as exception:
            last_error = exception
            continue
    raise OAuthError(
        OAuthErrorCode.DISCOVERY_FAILED,
        "Authorization server metadata discovery failed.",
        details={"issuer": issuer, **({"cause": str(last_error)} if last_error else {})},
    )


def _build_protected_resource_well_known_urls(resource: str) -> tuple[str, ...]:
    parsed = urlparse(resource)
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("OAuth protected resource must be an absolute URL.")
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    path = parsed.path or "/"
    if path != "/" and not path.startswith("/"):
        path = f"/{path}"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if path != "/" and path:
        return (
            urljoin(origin, f"/.well-known/oauth-protected-resource{path}"),
            urljoin(origin, "/.well-known/oauth-protected-resource"),
        )
    return (urljoin(origin, "/.well-known/oauth-protected-resource"),)


def _build_authorization_server_metadata_urls(issuer: str) -> tuple[str, ...]:
    parsed = urlparse(issuer)
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("OAuth issuer must be an absolute URL.")
    normalized_issuer = issuer.removesuffix("/")
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    path = parsed.path or ""
    if path and not path.startswith("/"):
        path = f"/{path}"
    if path.endswith("/") and path != "/":
        path = path[:-1]
    if not path or path == "/":
        return (
            f"{normalized_issuer}/.well-known/oauth-authorization-server",
            f"{normalized_issuer}/.well-known/openid-configuration",
        )
    return (
        urljoin(origin, f"/.well-known/oauth-authorization-server{path}"),
        urljoin(origin, f"/.well-known/openid-configuration{path}"),
    )


async def _fetch_json_dict(
    http_client: OAuthHTTPClientProtocol,
    url: str,
    *,
    timeout_sec: float,
) -> JSONDict:
    response = await http_client.get(
        url,
        headers={"Accept": "application/json"},
        timeout=timeout_sec,
    )
    if response.status_code != 200:
        raise OAuthError(
            OAuthErrorCode.DISCOVERY_FAILED,
            f"HTTP {response.status_code} while fetching OAuth metadata.",
            details={"url": url},
        )
    try:
        payload = read_http_json_dict(response, field="OAuth metadata response")
    except ValidationError as exception:
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            str(exception),
            details={"url": url},
        ) from exception
    return payload


def _parse_protected_resource_metadata(payload: JSONDict) -> OAuthProtectedResourceMetadata:
    resource = payload.get("resource")
    resource_str = resource if isinstance(resource, str) and resource.strip() else None
    auth_servers = payload.get("authorization_servers")
    servers: list[str] = []
    if isinstance(auth_servers, list):
        for entry in auth_servers:
            if isinstance(entry, str) and entry.strip():
                candidate = entry.strip()
                if _is_absolute_url(candidate):
                    servers.append(candidate)
    scopes_supported_value = payload.get("scopes_supported")
    scopes_supported: tuple[str, ...] | None = None
    if isinstance(scopes_supported_value, list):
        scopes: list[str] = []
        for entry in scopes_supported_value:
            if isinstance(entry, str) and entry.strip():
                scopes.append(entry.strip())
        scopes_supported = tuple(scopes) if scopes else None
    if not servers:
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Protected resource metadata missing authorization_servers.",
        )
    return OAuthProtectedResourceMetadata(
        resource=resource_str,
        authorization_servers=tuple(servers),
        scopes_supported=scopes_supported,
        raw=dict(payload),
    )


def _parse_authorization_server_metadata(payload: JSONDict) -> OAuthAuthorizationServerMetadata:
    issuer = payload.get("issuer")
    auth_endpoint = payload.get("authorization_endpoint")
    token_endpoint = payload.get("token_endpoint")
    if not (isinstance(issuer, str) and issuer.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Authorization server metadata missing issuer.",
        )
    if not (isinstance(auth_endpoint, str) and auth_endpoint.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Authorization server metadata missing authorization_endpoint.",
        )
    if not (isinstance(token_endpoint, str) and token_endpoint.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Authorization server metadata missing token_endpoint.",
        )
    if not _is_absolute_url(issuer.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Authorization server issuer must be an absolute URL.",
        )
    if not _is_absolute_url(auth_endpoint.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Authorization endpoint must be an absolute URL.",
        )
    if not _is_absolute_url(token_endpoint.strip()):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Token endpoint must be an absolute URL.",
        )
    registration_endpoint_value = payload.get("registration_endpoint")
    registration_endpoint = (
        registration_endpoint_value.strip()
        if isinstance(registration_endpoint_value, str) and registration_endpoint_value.strip()
        else None
    )
    if registration_endpoint and not _is_absolute_url(registration_endpoint):
        raise OAuthError(
            OAuthErrorCode.INVALID_METADATA,
            "Registration endpoint must be an absolute URL.",
        )
    token_auth_supported = _coerce_str_tuple(payload.get("token_endpoint_auth_methods_supported"))
    code_challenge_methods = _coerce_str_tuple(payload.get("code_challenge_methods_supported"))
    client_id_metadata_doc_supported = payload.get("client_id_metadata_document_supported") is True
    return OAuthAuthorizationServerMetadata(
        issuer=issuer.strip(),
        authorization_endpoint=auth_endpoint.strip(),
        token_endpoint=token_endpoint.strip(),
        registration_endpoint=registration_endpoint,
        token_endpoint_auth_methods_supported=token_auth_supported,
        code_challenge_methods_supported=code_challenge_methods,
        client_id_metadata_document_supported=client_id_metadata_doc_supported,
        raw=dict(payload),
    )


def _coerce_str_tuple(value: JSONValue) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            items.append(entry.strip())
    return tuple(items) if items else None


def _is_absolute_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)
