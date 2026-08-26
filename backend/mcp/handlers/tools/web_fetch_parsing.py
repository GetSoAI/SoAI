"""SoAI - Shared web_fetch input parsing [backend/mcp/handlers/tools/web_fetch_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import require_strict_int_at_least
from core.errors.exceptions import ValidationError
from core.mcp.argument_numbers import parse_timeout_ms_value
from mcp.protocol.types import MCPJSONRPCError
from mcp.shared.protocol_arguments import build_invalid_params_error
from mcp.tools.argument_scalars import parse_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "require_extract_mode",
    "resolve_effective_max_chars",
    "resolve_include_screenshot",
    "resolve_max_chars",
    "resolve_timeout_ms",
)

_MIN_MAX_CHARS: int = 1000
_MAX_MAX_CHARS: int = 500_000
_DEFAULT_MAX_CHARS_KEY = "TOOLS.MCP.WEB_FETCH.DEFAULT_MAX_CHARS"
_MAX_CHARS_LIMIT_KEY = "TOOLS.MCP.WEB_FETCH.MAX_CHARS_LIMIT"


def require_extract_mode(arguments: JSONDict) -> str:
    raw = arguments.get("extract_mode")
    if raw is None:
        return "markdown"
    if not isinstance(raw, str):
        raise MCPJSONRPCError(-32602, "extract_mode must be 'markdown', 'text', or 'html'")
    value = raw.strip().lower()
    if value in {"markdown", "text", "html"}:
        return value
    raise MCPJSONRPCError(-32602, "extract_mode must be 'markdown', 'text', or 'html'")


def resolve_max_chars(arguments: JSONDict, *, default: int) -> int:
    parsed = parse_int(
        arguments.get("max_chars"),
        default=default,
        min_value=_MIN_MAX_CHARS,
        max_value=_MAX_MAX_CHARS,
    )
    return int(parsed)


def resolve_effective_max_chars(config: ConfigProtocol, arguments: JSONDict) -> int:
    try:
        default_max_chars = require_strict_int_at_least(
            config.get_int(_DEFAULT_MAX_CHARS_KEY),
            key=_DEFAULT_MAX_CHARS_KEY,
            minimum=_MIN_MAX_CHARS,
        )
        max_chars_limit = require_strict_int_at_least(
            config.get_int(_MAX_CHARS_LIMIT_KEY),
            key=_MAX_CHARS_LIMIT_KEY,
            minimum=_MIN_MAX_CHARS,
        )
    except ValidationError as exception:
        raise MCPJSONRPCError(-32603, str(exception)) from exception
    requested = resolve_max_chars(arguments, default=default_max_chars)
    return int(min(max_chars_limit, requested))


def resolve_include_screenshot(arguments: JSONDict, *, default: bool) -> bool:
    screenshot_raw = arguments.get("screenshot")
    if screenshot_raw is None:
        return bool(default)
    if not isinstance(screenshot_raw, bool):
        raise MCPJSONRPCError(-32602, "screenshot must be a boolean when provided")
    return bool(screenshot_raw)


def resolve_timeout_ms(arguments: JSONDict) -> int | None:
    timeout_ms = parse_timeout_ms_value(
        arguments.get("timeout_ms"),
        field_name="timeout_ms",
        build_error=build_invalid_params_error,
        allow_none=True,
        allow_zero=False,
        minimum=1,
        maximum=300_000,
        range_message="timeout_ms must be between 1 and 300000",
    )
    if timeout_ms is None:
        return None
    return int(timeout_ms)
