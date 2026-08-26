"""SoAI - API runtime singleton bundle [backend/features/api/runtime/container/api_runtime_singletons.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.di.validation import require_dependencies
from core.mcp.tool_catalog_cache import MCPToolCatalogCache
from core.state.access_policy import AccessPolicyCache
from features.api.middleware.security.types import ProxyHeaderAnomalyTracker
from features.api.runtime.attachment_parse_tasks import AttachmentParseTaskRegistry
from features.api.runtime.chat_stream_registry import ChatStreamRegistry
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.container.security_runtime_state import SecurityRuntimeState
from features.api.runtime.container.soai_link_resolve_limiter import (
    SoaiLinkResolveConcurrencyLimiter,
)
from features.api.streaming.stream_channel_registry import TaskStreamChannelRegistry

if TYPE_CHECKING:
    from core.security.protocols import PasswordServiceProtocol

__all__ = ("ApiRuntimeSingletons",)


@dataclass(frozen=True, slots=True)
class ApiRuntimeSingletons:
    mcp_tool_catalog_cache: MCPToolCatalogCache
    access_policy_cache: AccessPolicyCache
    proxy_header_anomaly_tracker: ProxyHeaderAnomalyTracker
    security_runtime_state: SecurityRuntimeState
    login_attempt_locks: TTLAsyncLockRegistry[str]
    login_password_pool: BoundedBlockingPool
    login_password_service: PasswordServiceProtocol
    prompts_update_locks: TTLAsyncLockRegistry[int]
    conversation_rag_ingest_locks: TTLAsyncLockRegistry[str]
    conversation_agent_settings_locks: TTLAsyncLockRegistry[tuple[int, str]]
    enqueue_warning_tracker: EnqueueWarningTracker
    multipart_parser_semaphore: asyncio.Semaphore
    provider_video_projection_semaphore: asyncio.Semaphore
    stream_channel_registry: TaskStreamChannelRegistry
    chat_stream_registry: ChatStreamRegistry
    soai_link_resolve_limiter: SoaiLinkResolveConcurrencyLimiter
    attachment_parse_tasks: AttachmentParseTaskRegistry

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiRuntimeSingletons",
            mcp_tool_catalog_cache=self.mcp_tool_catalog_cache,
            access_policy_cache=self.access_policy_cache,
            proxy_header_anomaly_tracker=self.proxy_header_anomaly_tracker,
            security_runtime_state=self.security_runtime_state,
            login_attempt_locks=self.login_attempt_locks,
            login_password_pool=self.login_password_pool,
            login_password_service=self.login_password_service,
            prompts_update_locks=self.prompts_update_locks,
            conversation_rag_ingest_locks=self.conversation_rag_ingest_locks,
            conversation_agent_settings_locks=self.conversation_agent_settings_locks,
            enqueue_warning_tracker=self.enqueue_warning_tracker,
            multipart_parser_semaphore=self.multipart_parser_semaphore,
            provider_video_projection_semaphore=self.provider_video_projection_semaphore,
            stream_channel_registry=self.stream_channel_registry,
            chat_stream_registry=self.chat_stream_registry,
            soai_link_resolve_limiter=self.soai_link_resolve_limiter,
            attachment_parse_tasks=self.attachment_parse_tasks,
        )
