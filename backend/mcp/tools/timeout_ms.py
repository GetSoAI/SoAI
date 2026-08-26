"""SoAI - MCP timeout parsing [backend/mcp/tools/timeout_ms.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric_lenient import coerce_timeout_milliseconds_or_none
from core.mcp.argument_numbers import parse_timeout_ms_value
from mcp.tools.error import build_invalid_params_error

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "resolve_timeout_ms",
    "timeout_ms_to_seconds",
)


def resolve_timeout_ms(
    arguments: JSONDict,
    *,
    field_name: str,
    config: ConfigProtocol,
    config_key: str,
    default_timeout_ms: int | None,
) -> int | None:
    if field_name in arguments:
        return parse_timeout_ms_value(
            arguments[field_name],
            field_name=field_name,
            build_error=build_invalid_params_error,
            allow_none=True,
            allow_zero=True,
        )
    return coerce_timeout_milliseconds_or_none(
        config.get(config_key),
        default=default_timeout_ms,
    )


def timeout_ms_to_seconds(timeout_ms: int | None) -> float | None:
    if timeout_ms is None:
        return None
    return max(0.0, float(int(timeout_ms))) / 1000.0
