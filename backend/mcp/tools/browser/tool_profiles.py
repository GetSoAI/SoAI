"""SoAI - Browser tool: browser_profiles [backend/mcp/tools/browser/tool_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.network.urls import format_host_for_url, format_host_port_netloc
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.browser.profile_config import resolve_profile_config
from mcp.tools.browser.session_access import (
    parse_browser_profile,
    parse_browser_session_scope,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_profiles",)


def _redact_cdp_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https", "ws", "wss"}:
        return "<redacted>"
    host = str(parsed.hostname or "").strip()
    if not host:
        return "<redacted>"
    port = parsed.port
    if port is None:
        return f"{scheme}://{format_host_for_url(host)}"
    return f"{scheme}://{format_host_port_netloc(host, int(port))}"


def _resolve_profiles(utility_tools: MCPUtilityToolsProtocol) -> list[JSONDict]:
    raw_profiles = utility_tools.config.get("TOOLS.MCP.BROWSER.PROFILES", {}) or {}
    if not isinstance(raw_profiles, Mapping):
        raise ValidationError("TOOLS.MCP.BROWSER.PROFILES must be an object.")
    names: list[str] = ["default"]
    for key in raw_profiles:
        if not isinstance(key, str) or not key.strip():
            continue
        name = key.strip()
        if name not in names:
            names.append(name)
    profiles: list[JSONDict] = []
    for name in names:
        cfg = resolve_profile_config(utility_tools.config, profile=name)
        entry: JSONDict = {
            "name": cfg.name,
            "has_remote_cdp": cfg.cdp_url is not None,
            "persistence_mode": str(cfg.persistence or "").strip() or "storage_state",
            "headless": cfg.headless,
            "channel": cfg.channel,
            "locale": cfg.locale,
            "timezone_id": cfg.timezone_id,
            "accept_language": cfg.accept_language,
            "viewport_width": cfg.viewport_width,
            "viewport_height": cfg.viewport_height,
            "device_scale_factor": cfg.device_scale_factor,
        }
        if cfg.cdp_url is not None:
            entry["cdp_url"] = _redact_cdp_url(cfg.cdp_url)
        profiles.append(entry)
    return profiles


async def tool_browser_profiles(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(arguments, allowed_keys=frozenset(), tool_name="browser_profiles")
    try:
        profiles = _resolve_profiles(utility_tools)
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    return {
        "default_profile": parse_browser_profile({}, config=utility_tools.config),
        "default_session_scope": parse_browser_session_scope({}, config=utility_tools.config),
        "profiles": profiles,
    }
