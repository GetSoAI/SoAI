"""SoAI - MCP server shared mutable state [backend/mcp/server/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import weakref
from dataclasses import dataclass, field
from re import Pattern
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.concurrency.task_groups import ManagedTaskGroup
    from core.mcp.protocols_main import MCPSearchProtocol
    from mcp.protocol.types import (
        MCPClientSession,
        PromptHandler,
        ResourceHandler,
        SSEReplayBuffer,
        ToolHandler,
    )
    from mcp.rag.service import MCPRAG
    from mcp.search.api_keys import SearchProviderApiKeys
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "MCPRegistrationState",
    "MCPServerPendingRequestKey",
    "MCPServerState",
    "MCPSessionState",
    "MCPStreamingState",
    "MCPTaskState",
)


@dataclass(slots=True)
class MCPSessionState:
    client_sessions: dict[str, MCPClientSession] = field(
        default_factory=dict[str, "MCPClientSession"],
    )
    client_sessions_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    client_to_session: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(slots=True)
class MCPStreamingState:
    notification_queues: dict[str, asyncio.Queue[JSONDict | None]] = field(
        default_factory=dict[str, asyncio.Queue[JSONDict | None]],
    )
    stream_consumer_counts: dict[str, int] = field(default_factory=dict[str, int])
    sse_event_counters: dict[str, int] = field(default_factory=dict[str, int])
    sse_replay_buffers: dict[str, SSEReplayBuffer] = field(
        default_factory=dict[str, "SSEReplayBuffer"],
    )


@dataclass(frozen=True, slots=True)
class MCPServerPendingRequestKey:
    session_id: str
    rpc_id: str | int


@dataclass(slots=True)
class MCPTaskState:
    task_coroutines: dict[str, asyncio.Task[None]] = field(
        default_factory=dict[str, asyncio.Task[None]],
    )
    proxied_task_map: dict[str, str] = field(default_factory=dict[str, str])
    proxied_task_map_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_server_requests: dict[MCPServerPendingRequestKey, asyncio.Task[JSONValue]] = field(
        default_factory=dict[MCPServerPendingRequestKey, asyncio.Task[JSONValue]],
    )
    pending_server_requests_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task_method_map: weakref.WeakKeyDictionary[asyncio.Task[JSONValue], str] = field(
        default_factory=WeakKeyDictionary[asyncio.Task[JSONValue], str],
    )


@dataclass(slots=True)
class MCPRegistrationState:
    registered_tools: dict[str, ToolHandler] = field(default_factory=dict[str, "ToolHandler"])
    registered_resources: dict[str, ResourceHandler] = field(
        default_factory=dict[str, "ResourceHandler"],
    )
    registered_prompts: dict[str, PromptHandler] = field(default_factory=dict[str, "PromptHandler"])
    resource_subscriptions: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    resource_subscriptions_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass(slots=True)
class MCPServerState:
    session: MCPSessionState = field(default_factory=MCPSessionState)
    streaming: MCPStreamingState = field(default_factory=MCPStreamingState)
    task: MCPTaskState = field(default_factory=MCPTaskState)
    registration: MCPRegistrationState = field(default_factory=MCPRegistrationState)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    server_mode_active: bool = False
    rag_resource_patterns: dict[str, Pattern[str]] = field(default_factory=dict[str, Pattern[str]])
    mcp_rag: MCPRAG | None = None
    mcp_search: MCPSearchProtocol | None = None
    mcp_search_api_keys: SearchProviderApiKeys | None = None
    utility_tools: MCPUtilityTools | None = None
    background_tasks: ManagedTaskGroup | None = None
