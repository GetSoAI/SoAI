"""SoAI - MCP origin validation dependency [backend/features/api/routes/mcp/routes/origin_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import fnmatch
import ipaddress
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeGuard
from urllib.parse import urlsplit

from fastapi import Depends, Request

from core.config.value_validation import is_config_value
from core.mcp.protocols_main import MCPServerProtocol
from core.types.json import is_json_dict
from features.api.middleware.security.same_origin import origin_matches_request_host
from features.api.middleware.security.websocket_origins import (
    compile_websocket_origin_regex,
)
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_forbidden
from features.api.runtime.user_types import CurrentUser

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue
    from core.types.json import JSONValue

__all__ = (
    "resolve_current_user_id",
    "validate_mcp_origin",
)


def _is_localhost_client(request: Request) -> bool:
    client_host = request.client.host if request.client else None
    if not client_host:
        return False
    if request.headers.get("forwarded") or request.headers.get("x-forwarded-for"):
        return False
    normalized_host = client_host.strip().lower()
    if normalized_host == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def _origin_matches_pattern(origin: str, pattern: str) -> bool:
    if pattern == "*":
        return True
    if "*" in pattern:
        return fnmatch.fnmatch(origin, pattern)
    return origin == pattern


def _is_loopback_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        if not _origin_port_is_valid(parsed.port):
            return False
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return False
    host = parsed.hostname
    if host is None:
        return False
    normalized_host = host.strip().lower()
    if normalized_host == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def _origin_port_is_valid(port: int | None) -> bool:
    return port is None or port >= 0


def _is_origin_collection(
    value: ConfigValue | None,
) -> TypeGuard[tuple[str, ...] | list[str] | set[str] | frozenset[str]]:
    if not isinstance(value, tuple | list | set | frozenset):
        return False
    return all(isinstance(item, str) for item in value)


async def validate_mcp_origin(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> MCPServerProtocol:
    mcp_server_instance = api_context.dependencies.mcp_server
    origin = request.headers.get("origin")
    if not origin:
        if _is_localhost_client(request):
            return mcp_server_instance
        mcp_allowed_origins = mcp_server_instance.allowed_origins
        if not mcp_allowed_origins:
            return mcp_server_instance
        if "*" in mcp_allowed_origins:
            return mcp_server_instance
        return raise_forbidden(
            request,
            "Origin header required when MCP allowed_origins is configured",
            error_type="origin_required",
        )
    mcp_allowed_origins = mcp_server_instance.allowed_origins
    if mcp_allowed_origins:
        for pattern in mcp_allowed_origins:
            if _origin_matches_pattern(origin, pattern):
                return mcp_server_instance
        return raise_forbidden(
            request,
            f"Origin '{origin}' is not allowed for MCP requests",
            error_type="origin_not_allowed",
        )
    if _is_localhost_client(request):
        if _is_loopback_origin(origin):
            return mcp_server_instance
    if origin_matches_request_host(origin, request.headers.get("host"), request.url.scheme):
        return mcp_server_instance
    try:
        app_state = request.app.state
    except AttributeError:
        app_state = None
    if app_state is None:
        return raise_forbidden(
            request,
            f"Origin '{origin}' is not allowed",
            error_type="origin_not_allowed",
        )
    try:
        cors_trusted_origins_value = app_state.cors_trusted_origins
    except AttributeError:
        cors_trusted_origins_value = ()
    if is_config_value(cors_trusted_origins_value) and _is_origin_collection(
        cors_trusted_origins_value,
    ):
        cors_trusted_origins = cors_trusted_origins_value
    else:
        cors_trusted_origins = ()
    try:
        cors_config_value = app_state.cors_config
    except AttributeError:
        cors_config_value = None
    cors_config: Mapping[str, JSONValue] = (
        cors_config_value if is_json_dict(cors_config_value) else {}
    )
    allow_origin_regex = cors_config.get("allow_origin_regex")
    if cors_trusted_origins and origin in cors_trusted_origins:
        return mcp_server_instance
    if isinstance(allow_origin_regex, str) and allow_origin_regex:
        compiled_regex = compile_websocket_origin_regex(allow_origin_regex)
        if compiled_regex and compiled_regex.fullmatch(origin):
            return mcp_server_instance
    return raise_forbidden(
        request,
        f"Origin '{origin}' is not allowed",
        error_type="origin_not_allowed",
    )


def resolve_current_user_id(current_user: CurrentUser | None) -> int:
    if current_user is None:
        return 0
    return current_user["id"]
