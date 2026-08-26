"""SoAI - API runtime singleton construction [backend/app/composition/build_api_runtime_singletons.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable

from core.concurrency.bounded_blocking import (
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
    shutdown_bounded_pool_executor,
)
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.config.numeric import coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.mcp.tool_catalog_cache import MCPToolCatalogCache
from core.runtime.soai_identifiers import create_system_id
from core.security.password_hashing import PasswordContext
from core.security.password_service import PasswordService, PasswordServiceDependencies
from core.state.access_policy import AccessPolicyCache
from core.tasks.asyncio_task_spawner import create_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from features.api.middleware.security.types import ProxyHeaderAnomalyTracker
from features.api.runtime.attachment_parse_tasks import (
    AttachmentParseTaskRegistry,
    AttachmentParseTaskRegistryDependencies,
)
from features.api.runtime.chat_stream_registry import (
    ChatStreamRegistry,
    ChatStreamRegistryDependencies,
)
from features.api.runtime.container.api_runtime_singletons import ApiRuntimeSingletons
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.container.security_runtime_state import SecurityRuntimeState
from features.api.runtime.container.soai_link_resolve_limiter import (
    SoaiLinkResolveConcurrencyLimiter,
)
from features.api.runtime.webui_attachments.provider_video_settings import (
    read_provider_video_settings,
)
from features.api.streaming.stream_channel_registry import (
    TaskStreamChannelRegistry,
    TaskStreamChannelRegistryDependencies,
)

__all__ = ("build_api_runtime_singletons",)

LOGGER_NAME_API_RUNTIME_SINGLETONS = "SoAI.app.composition.build_api_runtime_singletons"
_DEFAULT_MULTIPART_PARSER_MAX_CONCURRENT = 8
_MAX_MULTIPART_PARSER_MAX_CONCURRENT = 256


def build_api_runtime_singletons(
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    config: ConfigProtocol,
    event_bus: EventBusProtocol,
) -> ApiRuntimeSingletons:
    async def spawn_attachment_parse_task(
        attachment_id: str,
        awaitable: Awaitable[None],
    ) -> asyncio.Task[None]:
        task = await create_tracked_task(
            awaitable,
            name=f"webui-attachment-parse:{attachment_id}",
            logger=get_logger(LOGGER_NAME_API_RUNTIME_SINGLETONS),
            cancellation_binder=cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="attachment_parse",
                owner=attachment_id,
                include_random_suffix=False,
            ),
            owner="webui_chat_attachment_parse",
            metadata={"attachment_id": attachment_id},
        )
        finalizer_tracker.track_finalizer(task)
        return task

    multipart_parser_limit = coerce_positive_int(
        os.getenv("SOAI_MULTIPART_PARSER_MAX_CONCURRENT", None),
        default=_DEFAULT_MULTIPART_PARSER_MAX_CONCURRENT,
        minimum=1,
        maximum=_MAX_MULTIPART_PARSER_MAX_CONCURRENT,
        label="SOAI_MULTIPART_PARSER_MAX_CONCURRENT",
        logger=None,
    )
    provider_video_settings = read_provider_video_settings(config)
    login_password_pool = create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="webui-login-password-verification",
            thread_name_prefix="soai-login-pw",
            max_workers_env="SOAI_WEBUI_LOGIN_PASSWORD_MAX_WORKERS",
            max_in_flight_env="SOAI_WEBUI_LOGIN_PASSWORD_MAX_IN_FLIGHT",
            default_max_workers=2,
            minimum_workers=1,
            maximum_workers=8,
            default_in_flight_multiplier=2,
            default_min_in_flight=4,
            max_in_flight_limit=32,
        ),
    )
    runtime_singletons: ApiRuntimeSingletons | None = None
    try:
        runtime_singletons = ApiRuntimeSingletons(
            mcp_tool_catalog_cache=MCPToolCatalogCache(),
            access_policy_cache=AccessPolicyCache(),
            proxy_header_anomaly_tracker=ProxyHeaderAnomalyTracker(),
            security_runtime_state=SecurityRuntimeState(),
            login_attempt_locks=TTLAsyncLockRegistry[str](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=1800.0,
                    max_size=50000,
                    cleanup_interval_seconds=300.0,
                ),
            ),
            login_password_pool=login_password_pool,
            login_password_service=PasswordService(
                PasswordServiceDependencies(
                    pool=login_password_pool,
                    password_context=PasswordContext(),
                ),
            ),
            prompts_update_locks=TTLAsyncLockRegistry[int](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=1800.0,
                    max_size=5000,
                    cleanup_interval_seconds=300.0,
                ),
            ),
            conversation_rag_ingest_locks=TTLAsyncLockRegistry[str](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=1800.0,
                    max_size=5000,
                    cleanup_interval_seconds=300.0,
                ),
            ),
            conversation_agent_settings_locks=TTLAsyncLockRegistry[tuple[int, str]](
                TTLAsyncLockRegistryDependencies(
                    ttl_seconds=1800.0,
                    max_size=5000,
                    cleanup_interval_seconds=300.0,
                ),
            ),
            enqueue_warning_tracker=EnqueueWarningTracker(),
            multipart_parser_semaphore=asyncio.Semaphore(multipart_parser_limit),
            provider_video_projection_semaphore=asyncio.Semaphore(
                provider_video_settings.max_concurrent_projections,
            ),
            stream_channel_registry=TaskStreamChannelRegistry(
                TaskStreamChannelRegistryDependencies(),
            ),
            chat_stream_registry=ChatStreamRegistry(
                ChatStreamRegistryDependencies(event_bus=event_bus),
            ),
            soai_link_resolve_limiter=SoaiLinkResolveConcurrencyLimiter(),
            attachment_parse_tasks=AttachmentParseTaskRegistry(
                AttachmentParseTaskRegistryDependencies(
                    task_spawner=spawn_attachment_parse_task,
                ),
            ),
        )
    finally:
        if runtime_singletons is None:
            shutdown_bounded_pool_executor(login_password_pool)
    if runtime_singletons is None:
        raise StateError("API runtime singleton construction completed without a result.")
    return runtime_singletons
