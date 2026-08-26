"""SoAI - API runtime feature flags [backend/features/api/runtime/feature_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.config.protocols import ConfigProtocol
from core.validation.booleans import parse_bool_token_or_none
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found

__all__ = (
    "mcp_feature_enabled",
    "require_mcp_feature_enabled",
    "terminal_feature_enabled",
)


def terminal_feature_enabled(config: ConfigProtocol) -> bool:
    return config.get_bool("SERVER.WEBUI.TERMINAL.ENABLED")


def mcp_feature_enabled(config: ConfigProtocol) -> bool:
    raw_value = config.get("TOOLS.MCP.ENABLED")
    if raw_value is None:
        return False
    parsed = parse_bool_token_or_none(raw_value)
    if parsed is not None:
        return parsed
    if isinstance(raw_value, str):
        return bool(raw_value.strip())
    if isinstance(raw_value, int | float) and not isinstance(raw_value, bool):
        return bool(raw_value)
    return False


async def require_mcp_feature_enabled(request: Request) -> ApiContext:
    api_context = resolve_api_context(request)
    if not mcp_feature_enabled(api_context.dependencies.config):
        raise_not_found(request, "MCP API is disabled.")
    return api_context
