"""SoAI - WebSocket chat stream runner [backend/features/api/routes/system/events/websocket_chat_stream/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tool_calls.status_values import TOOL_CALL_STATUS_COMPLETED
from features.api.routes.system.events.websocket_chat_stream.agent_streaming import (
    create_ws_chat_agent_stream,
)
from features.api.routes.system.events.websocket_chat_stream.agent_turn_admission import (
    start_ws_chat_stream_agent_turn_admission,
)
from features.api.routes.system.events.websocket_chat_stream.completion_followups import (
    track_auto_title_generation,
)
from features.api.routes.system.events.websocket_chat_stream.exit_terminal_reconciliation import (
    reconcile_unterminated_ws_chat_stream_exit,
)
from features.api.routes.system.events.websocket_chat_stream.failure_cleanup import (
    cleanup_ws_chat_stream_failure_noncritical,
)
from features.api.routes.system.events.websocket_chat_stream.finalization import (
    finalize_ws_chat_stream_cancellation_noncritical,
    finalize_ws_chat_stream_error_noncritical,
)
from features.api.routes.system.events.websocket_chat_stream.stream_admission import (
    start_ws_chat_stream_admission,
)
from features.api.routes.system.events.websocket_chat_stream.stream_run_phases import (
    abort_admitted_ws_chat_stream_if_cancelled,
    abort_ws_chat_stream_before_admission_if_cancelled,
    run_ws_chat_stream_non_agent_arm,
)
from features.api.routes.system.events.websocket_chat_stream.terminal_state import (
    resolve_ws_chat_stream_terminal_turn_state,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_noncritical,
)
from features.assistant_timeline.agentic_outcome import resolve_agentic_terminal_outcome
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_agentic_stream_timeline,
)
from features.chat.conversation_timeline_session import (
    create_assistant_timeline_session,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("run_ws_chat_stream",)

LOGGER_NAME = "SoAI.features.api.websocket_chat_stream_runner"
OPERATION = "api_system.ws_chat_stream.run_ws_chat_stream"
WS_CHAT_STREAM_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def run_ws_chat_stream(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    webui_manager = api_context.dependencies.webui_manager
    registry: TaskRegistryProtocol = api_context.dependencies.task_registry
    context = request_context
    session = create_assistant_timeline_session(
        api_dependencies=api_context.dependencies,
        runtime=runtime,
        collect_tool_calls=tool_context is not None,
        status_preview_enabled=True,
    )
    try:
        if await abort_ws_chat_stream_before_admission_if_cancelled(
            api_context=api_context,
            session=session,
            context=context,
            tool_context=tool_context,
            knowledge_prompt_claim=knowledge_prompt_claim,
            logger=logger,
        ):
            return
        cancel_on_disconnect = api_context.dependencies.config.get_bool(
            "MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT",
        )
        if tool_context is None:
            bundle = await start_ws_chat_stream_admission(
                session=session,
                api_context=api_context,
                request_context=context,
                runtime=runtime,
                request_json=request_json,
                tool_context=tool_context,
                prepared_agent_request=prepared_agent_request,
                knowledge_prompt_claim=knowledge_prompt_claim,
                logger=logger,
            )
            if await abort_admitted_ws_chat_stream_if_cancelled(
                api_context=api_context,
                session=session,
                context=context,
                tool_context=tool_context,
                bundle=bundle,
                logger=logger,
            ):
                return
            await run_ws_chat_stream_non_agent_arm(
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                session=session,
                context=context,
                bundle=bundle,
                registry=registry,
            )
            return
        first_iteration_cancellation_id = await start_ws_chat_stream_agent_turn_admission(
            session=session,
            api_context=api_context,
            request_context=context,
            runtime=runtime,
            tool_context=tool_context,
            prepared_agent_request=prepared_agent_request,
            knowledge_prompt_claim=knowledge_prompt_claim,
            logger=logger,
        )
        if runtime.cancellation_requested:
            await release_ws_chat_stream_runtime_quota_noncritical(
                database_api_keys=webui_manager.database_api_keys,
                runtime=runtime,
                logger=logger,
                trace_id=context.trace_id,
                operation="webui_ws_chat_stream.run.release_quota_after_agent_turn_cancel",
                message="Failed to release chat stream quota after agent turn cancellation.",
            )
            await finalize_ws_chat_stream_cancellation_noncritical(
                session=session,
                database_agent_turns=api_context.dependencies.database_agent_turns,
                task_registry=registry,
                logger=logger,
                context=context,
                tool_context=tool_context,
            )
            return
        stream_generator = create_ws_chat_agent_stream(
            request=request,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            context=context,
            runtime=runtime,
            request_json=request_json,
            task=None,
            reply_queue=None,
            required_capabilities=(),
            required_modalities=(),
            prepared_agent_request=prepared_agent_request,
            cancel_on_disconnect=cancel_on_disconnect,
            logger=logger,
            stream_transcript=session.stream_transcript,
            first_iteration_cancellation_id=first_iteration_cancellation_id,
        )
        await session.consume_stream(stream_generator)
        if runtime.cancellation_requested:
            await finalize_ws_chat_stream_cancellation_noncritical(
                session=session,
                database_agent_turns=api_context.dependencies.database_agent_turns,
                task_registry=registry,
                logger=logger,
                context=context,
                tool_context=tool_context,
            )
            return
        turn_state = await resolve_ws_chat_stream_terminal_turn_state(
            api_context=api_context,
            runtime=runtime,
            logger=logger,
            trace_id=context.trace_id,
        )

        async def resolved_turn_state_loader() -> JSONDict | None:
            return turn_state

        terminal_outcome = await finalize_agentic_stream_timeline(
            session,
            turn_state_loader=resolved_turn_state_loader,
            resolve_terminal_outcome=resolve_agentic_terminal_outcome,
        )
        if terminal_outcome == TOOL_CALL_STATUS_COMPLETED:
            track_auto_title_generation(
                api_dependencies=api_context.dependencies,
                runtime=runtime,
                task_name=f"ws-agent-auto-title-{runtime.conv_id}",
            )
        return
    except CancelledError:
        await uncancel_then_cleanup(
            release_ws_chat_stream_runtime_quota_noncritical(
                database_api_keys=webui_manager.database_api_keys,
                runtime=runtime,
                logger=logger,
                trace_id=context.trace_id,
                operation="webui_ws_chat_stream.run.release_quota_after_cancellation",
                message="Failed to release chat stream quota after cancellation.",
            ),
        )
        await uncancel_then_cleanup(
            finalize_ws_chat_stream_cancellation_noncritical(
                session=session,
                database_agent_turns=api_context.dependencies.database_agent_turns,
                task_registry=registry,
                logger=logger,
                context=context,
                tool_context=tool_context,
            ),
        )
        raise
    except WS_CHAT_STREAM_FAILURE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_system.ws_chat_stream.run_ws_chat_stream",
        )
        log_exception(
            logger,
            coerced,
            message="WebSocket chat stream failed",
            operation=OPERATION,
            trace_id=context.trace_id,
            details={
                "conv_id": runtime.conv_id,
                "user_id": runtime.user_id,
                "request_id": runtime.request_id,
            },
        )
        message, code = await cleanup_ws_chat_stream_failure_noncritical(
            exception,
            api_context=api_context,
            logger=logger,
            context=context,
            session=session,
            database_api_keys=webui_manager.database_api_keys,
        )
        await finalize_ws_chat_stream_error_noncritical(
            session=session,
            database_agent_turns=api_context.dependencies.database_agent_turns,
            task_registry=registry,
            logger=logger,
            context=context,
            tool_context=tool_context,
            error_message=message,
            error_code=code,
            turn_error_message=str(coerced),
            turn_error_type=str(coerced.code),
        )
    finally:
        await uncancel_then_cleanup(
            reconcile_unterminated_ws_chat_stream_exit(
                session=session,
                task_registry=registry,
                api_context=api_context,
                logger=logger,
                context=context,
                tool_context=tool_context,
            ),
        )
        await uncancel_then_cleanup(session.close())
