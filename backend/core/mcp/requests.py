"""SoAI - Core MCP request models shared between protocols and implementations [backend/core/mcp/requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("AddMCPServerRequest",)


@dataclass(frozen=True, slots=True)
class AddMCPServerRequest:
    name: str
    transport_type: str
    endpoint: str
    arguments: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    api_key: str | None = None
    timeout_ms: int = 30000
    auto_reconnect: bool = True
