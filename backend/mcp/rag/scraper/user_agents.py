"""SoAI - MCP web scraper user agent rotation [backend/mcp/rag/scraper/user_agents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from core.network.outbound_http_profiles import DEFAULT_BROWSER_DOCUMENT_USER_AGENTS

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = ("get_user_agent",)

DEFAULT_USER_AGENTS: tuple[str, ...] = DEFAULT_BROWSER_DOCUMENT_USER_AGENTS


def get_user_agent(self: WebContentFetcherProtocol) -> str:
    if not self.ua_rotation_enabled:
        return self.static_user_agent
    agents = self.ua_agents
    if not agents:
        return self.static_user_agent
    if self.ua_rotation_mode == "sequential":
        index = self.ua_sequential_index % len(agents)
        self.set_ua_sequential_index(self.ua_sequential_index + 1)
        return agents[index]
    return secrets.choice(agents)
