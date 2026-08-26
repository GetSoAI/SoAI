"""SoAI - WebSocket chat stream admission cleanup [backend/features/api/routes/system/events/websocket_chat_stream/admission_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, overload

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_noncritical,
)
from features.api.runtime.knowledge_prompt_delivery import (
    commit_knowledge_prompt_claim_noncritical,
    release_knowledge_prompt_claim_noncritical,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.logging.protocols import TraceLogger
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.request_context import RequestContext
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "commit_ws_chat_stream_knowledge_prompt_claim",
    "release_ws_chat_stream_admission_claims",
    "release_ws_chat_stream_knowledge_prompt_claim",
    "run_ws_chat_stream_admission_lifecycle",
)


async def release_ws_chat_stream_knowledge_prompt_claim(
    *,
    api_context: ApiContext,
    request_context: RequestContext,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
) -> None:
    await uncancel_then_cleanup(
        release_knowledge_prompt_claim_noncritical(
            api_dependencies=api_context.dependencies,
            claim=knowledge_prompt_claim,
            logger=logger,
            trace_id=request_context.trace_id,
        ),
    )


async def commit_ws_chat_stream_knowledge_prompt_claim(
    *,
    api_context: ApiContext,
    request_context: RequestContext,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
) -> None:
    await uncancel_then_cleanup(
        commit_knowledge_prompt_claim_noncritical(
            api_dependencies=api_context.dependencies,
            claim=knowledge_prompt_claim,
            logger=logger,
            trace_id=request_context.trace_id,
        ),
    )


async def release_ws_chat_stream_admission_claims(
    *,
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
    database_api_keys: DatabaseAPIKeysProtocol,
    quota_operation: str,
    quota_message: str,
) -> None:
    await release_ws_chat_stream_knowledge_prompt_claim(
        api_context=api_context,
        request_context=request_context,
        knowledge_prompt_claim=knowledge_prompt_claim,
        logger=logger,
    )
    await uncancel_then_cleanup(
        release_ws_chat_stream_runtime_quota_noncritical(
            database_api_keys=database_api_keys,
            runtime=runtime,
            logger=logger,
            trace_id=request_context.trace_id,
            operation=quota_operation,
            message=quota_message,
        ),
    )


@overload
async def run_ws_chat_stream_admission_lifecycle(
    *,
    admission: Callable[[], Awaitable[str]],
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
    database_api_keys: DatabaseAPIKeysProtocol,
    quota_operation: str,
    quota_message: str,
    release_on_unexpected: bool,
) -> str: ...


@overload
async def run_ws_chat_stream_admission_lifecycle(
    *,
    admission: Callable[[], Awaitable[AgentStreamingTaskBundle]],
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
    database_api_keys: DatabaseAPIKeysProtocol,
    quota_operation: str,
    quota_message: str,
    release_on_unexpected: bool,
) -> AgentStreamingTaskBundle: ...


async def run_ws_chat_stream_admission_lifecycle(
    *,
    admission: Callable[[], Awaitable[str | AgentStreamingTaskBundle]],
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
    database_api_keys: DatabaseAPIKeysProtocol,
    quota_operation: str,
    quota_message: str,
    release_on_unexpected: bool,
) -> str | AgentStreamingTaskBundle:
    try:
        result = await admission()
    except CancelledError:
        await release_ws_chat_stream_knowledge_prompt_claim(
            api_context=api_context,
            request_context=request_context,
            knowledge_prompt_claim=knowledge_prompt_claim,
            logger=logger,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await release_ws_chat_stream_admission_claims(
            api_context=api_context,
            request_context=request_context,
            runtime=runtime,
            knowledge_prompt_claim=knowledge_prompt_claim,
            logger=logger,
            database_api_keys=database_api_keys,
            quota_operation=quota_operation,
            quota_message=quota_message,
        )
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS:
        if release_on_unexpected:
            await release_ws_chat_stream_admission_claims(
                api_context=api_context,
                request_context=request_context,
                runtime=runtime,
                knowledge_prompt_claim=knowledge_prompt_claim,
                logger=logger,
                database_api_keys=database_api_keys,
                quota_operation=quota_operation,
                quota_message=quota_message,
            )
        raise
    await commit_ws_chat_stream_knowledge_prompt_claim(
        api_context=api_context,
        request_context=request_context,
        knowledge_prompt_claim=knowledge_prompt_claim,
        logger=logger,
    )
    return result
