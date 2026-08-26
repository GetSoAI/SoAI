"""SoAI - MCP server-mode tool exposure drift reporting [backend/mcp/server/handlers/exposure_drift.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("report_exposed_tools_drift",)


def report_exposed_tools_drift(
    *,
    exposed_tools: set[str] | None,
    known_tool_names: set[str],
    exposable_tool_names: set[str],
    logger: LoggerProtocol,
) -> None:
    if exposed_tools is None:
        return
    exposed_not_known = sorted(exposed_tools - known_tool_names)
    exposed_internal_only = sorted((exposed_tools & known_tool_names) - exposable_tool_names)
    known_not_exposed = sorted(exposable_tool_names - exposed_tools)
    if exposed_not_known:
        logger.warning(
            "MCP server mode TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS lists %d name(s) that match no usable tool (renamed or removed): %s",
            len(exposed_not_known),
            ", ".join(exposed_not_known),
        )
    if exposed_internal_only:
        logger.warning(
            "MCP server mode TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS lists %d internal-only tool name(s) that cannot be exposed: %s",
            len(exposed_internal_only),
            ", ".join(exposed_internal_only),
        )
    if known_not_exposed:
        logger.warning(
            "MCP server mode TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS omits %d usable tool(s); add them to expose over server mode: %s",
            len(known_not_exposed),
            ", ".join(known_not_exposed),
        )
