"""SoAI - MCP protocol version registry [backend/core/mcp/protocol_versions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "DEFAULT_NEGOTIATED_PROTOCOL_VERSION",
    "MCP_PROTOCOL_VERSION",
    "MCP_PROTOCOL_VERSION_2025_06_18",
    "MCP_PROTOCOL_VERSION_2025_11_25",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "validate_protocol_version",
)

MCP_PROTOCOL_VERSION_2025_06_18: str = "2025-06-18"
MCP_PROTOCOL_VERSION_2025_11_25: str = "2025-11-25"
MCP_PROTOCOL_VERSION: str = MCP_PROTOCOL_VERSION_2025_11_25

SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = (
    MCP_PROTOCOL_VERSION_2025_06_18,
    MCP_PROTOCOL_VERSION_2025_11_25,
)

DEFAULT_NEGOTIATED_PROTOCOL_VERSION: str = MCP_PROTOCOL_VERSION


def validate_protocol_version(version: str | None) -> tuple[bool, str]:
    if version is None:
        return (True, DEFAULT_NEGOTIATED_PROTOCOL_VERSION)
    return (version in SUPPORTED_PROTOCOL_VERSIONS, version)
