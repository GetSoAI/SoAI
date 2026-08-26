"""SoAI - Browser tool timeout resolution [backend/mcp/tools/browser/timeouts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "action_timeout_scope",
    "build_action_wall_clock_timeout_sec",
    "build_wall_clock_timeout_sec",
    "resolve_action_timeout_sec",
    "resolve_action_wall_clock_timeout_sec",
    "resolve_max_wait_sec",
)


def build_wall_clock_timeout_sec(
    *,
    timeout_ms: int | None,
    fallback_timeout_sec: float,
    extra_wait_ms: int,
    buffer_sec: float,
) -> float:
    requested_timeout_sec = float(fallback_timeout_sec)
    if timeout_ms is not None:
        requested_timeout_sec = float(timeout_ms) / 1000.0
    extra_wait_sec = 0.0
    if extra_wait_ms > 0:
        extra_wait_sec = float(extra_wait_ms) / 1000.0
    return max(1.0, requested_timeout_sec + extra_wait_sec + float(buffer_sec))


def resolve_action_timeout_sec(utility_tools: MCPUtilityToolsProtocol) -> int:
    raw = utility_tools.config.get_int("TOOLS.MCP.BROWSER.DEFAULT_ACTION_TIMEOUT_SEC")
    if not is_strict_int(raw):
        return 15
    return max(1, int(raw))


def build_action_wall_clock_timeout_sec(
    *,
    action_timeout_sec: int,
    stabilize_ms: int,
    timeout_ms: int | None,
    buffer_sec: float,
) -> float:
    return build_wall_clock_timeout_sec(
        timeout_ms=timeout_ms,
        fallback_timeout_sec=float(action_timeout_sec),
        extra_wait_ms=stabilize_ms,
        buffer_sec=buffer_sec,
    )


def resolve_action_wall_clock_timeout_sec(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    stabilize_ms: int,
    timeout_ms: int | None = None,
    buffer_sec: float = 10.0,
) -> float:
    return build_action_wall_clock_timeout_sec(
        action_timeout_sec=resolve_action_timeout_sec(utility_tools),
        stabilize_ms=stabilize_ms,
        timeout_ms=timeout_ms,
        buffer_sec=buffer_sec,
    )


def action_timeout_scope(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    stabilize_ms: int,
    timeout_ms: int | None = None,
    buffer_sec: float = 10.0,
) -> asyncio.Timeout:
    return asyncio.timeout(
        resolve_action_wall_clock_timeout_sec(
            utility_tools,
            stabilize_ms=stabilize_ms,
            timeout_ms=timeout_ms,
            buffer_sec=buffer_sec,
        ),
    )


def resolve_max_wait_sec(utility_tools: MCPUtilityToolsProtocol) -> float:
    raw = utility_tools.config.get_float("TOOLS.MCP.BROWSER.MAX_WAIT_SEC")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 300.0
    return max(1.0, min(3600.0, value))
