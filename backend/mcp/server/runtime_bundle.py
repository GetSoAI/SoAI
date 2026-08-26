"""SoAI - MCP server runtime wiring bundle [backend/mcp/server/runtime_bundle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.mcp.protocols_main import MCPSearchApiKeysProtocol, MCPSearchProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.service_lifecycle import ServiceLifecycle
from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
from mcp.server.component_factory import MCPServerComponents
from mcp.server.runtime_config import MCPRuntimeConfig
from mcp.server.state import MCPServerState

if TYPE_CHECKING:
    from core.concurrency.task_groups import ManagedTaskGroup
    from mcp.tools.service import MCPUtilityTools

__all__ = ("MCPServerRuntimeBundle",)


@dataclass(frozen=True, slots=True)
class MCPServerRuntimeBundle:
    lifecycle: ServiceLifecycle
    shutdown_event: asyncio.Event
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    background_tasks: ManagedTaskGroup
    web_fetcher: WebContentFetcherProtocol | None
    state: MCPServerState
    search: MCPSearchProtocol
    search_api_keys: MCPSearchApiKeysProtocol
    utility_tools: MCPUtilityTools
    runtime_config: MCPRuntimeConfig
    components: MCPServerComponents
