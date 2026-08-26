"""SoAI - Automation turn execution orchestration [backend/features/automation/execution_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.automation.automation_identifiers import build_automation_turn_request_id
from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.tool_context_identity_validation import (
    build_tool_context_message_index_mismatch_message,
)
from core.runtime.cancellation_ids import build_automation_turn_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_AUTOMATION
from features.agent.runtime.agentic_execution_policy import should_run_agent_turn_engine
from features.agent.runtime.turn_engine import AgentTurnEngineDependencies
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_assistant_timeline_error,
)
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)
from features.assistant_timeline.loading_error_finalization import (
    publish_initial_loading_activity,
)
from features.automation.execution_messages import (
    AutomationConversationSession,
    append_turn_user_message,
    commit_turn_assistant_message,
    reserve_turn_assistant_message,
)
from features.automation.execution_stream_lifecycle import (
    release_automation_stream_runtime,
)
from features.automation.execution_turn_finalization import (
    cancel_automation_turn_streaming_task_noncritical,
    finalize_automation_turn_cancelled,
)
from features.automation.execution_turn_request_preparation import (
    prepare_automation_turn_request,
)
from features.chat.conversation_agent_stream import execute_conversation_agent_stream
from features.chat.conversation_timeline_session import (
    create_assistant_timeline_session,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = ("execute_automation_turn",)

LOGGER_NAME = "SoAI.features.automation.execution_turns"
OPERATION_EXECUTE = "automation.execution_turns.execute"


def _build_turn_metadata(
    *,
    automation_id: str,
    run_id: str,
    turn_index: int,
    conv_id: str,
) -> JSONDict:
    return {
        "webui": True,
        "automation": True,
        "automation_id": automation_id,
        "automation_run_id": run_id,
        "turn_index": turn_index,
        "conv_id": conv_id,
    }


async def execute_automation_turn(
    api_dependencies: ApiDependencies,
    *,
    automation_id: str,
    run_id: str,
    turn_index: int,
    turn_text: str,
    conversation_model_settings: JSONDict,
    session: AutomationConversationSession,
    request_context: RequestContext,
    requested_model: str,
    agent_settings: AgentSettings,
    deps: AgentTurnEngineDependencies,
) -> str:
    await append_turn_user_message(api_dependencies, session, content=turn_text)
    turn_request_id = build_automation_turn_request_id(run_id, turn_index)
    turn_cancellation_id = build_automation_turn_cancellation_id(
        context_cancellation_id=str(request_context.cancellation_id or ""),
        run_id=run_id,
        turn_index=turn_index,
    )
    reserved_message = await reserve_turn_assistant_message(
        api_dependencies,
        session,
        model_id=requested_model,
        request_id=turn_request_id,
        task_cancellation_id=turn_cancellation_id,
    )
    runtime = reserved_message.runtime
    session_runtime: AssistantTimelineSession | None = None
    try:
        session_runtime = create_assistant_timeline_session(
            api_dependencies=api_dependencies,
            runtime=runtime,
            collect_tool_calls=True,
            status_preview_enabled=False,
        )
        turn_context = clone_request_context(
            request_context,
            cancellation_id=turn_cancellation_id,
        )
        metadata = _build_turn_metadata(
            automation_id=automation_id,
            run_id=run_id,
            turn_index=turn_index,
            conv_id=session.conv_id,
        )
        try:
            await publish_initial_loading_activity(
                runtime=runtime,
                event_bus=api_dependencies.event_bus,
                database_messages=api_dependencies.database_messages,
            )
            await publish_chat_stream_message_events(api_dependencies.event_bus, runtime)
            session_runtime.start()
            prepared_request = await prepare_automation_turn_request(
                api_dependencies,
                session=session,
                request_context=turn_context,
                conversation_model_settings=conversation_model_settings,
                requested_model=requested_model,
                agent_settings=agent_settings,
                assistant_at_ms=runtime.assistant_at_ms,
                assistant_message_index=runtime.message_index,
            )
            tool_context = prepared_request.tool_context
            prepared_agent_request = prepared_request.prepared_agent_request
            if not should_run_agent_turn_engine(
                agent_settings=agent_settings,
                tool_context=tool_context,
            ):
                raise StateError("Automation turns must execute via the agent engine.")
            if tool_context is None or prepared_agent_request is None:
                raise StateError(
                    "Automation turn agentic execution requires tool context and prepared request.",
                )
            if int(tool_context.message_index) != int(runtime.message_index):
                raise StateError(
                    build_tool_context_message_index_mismatch_message(
                        surface="Automation turn",
                        conv_id=session.conv_id,
                        assistant_at_ms=runtime.assistant_at_ms,
                        tool_context_message_index=tool_context.message_index,
                        runtime_message_index=runtime.message_index,
                    ),
                )
            prepared_payload = dict(prepared_agent_request.final_payload)
            await execute_conversation_agent_stream(
                api_dependencies,
                deps=deps,
                turn_context=turn_context,
                tool_context=tool_context,
                request_messages=[
                    dict(message)
                    for message in prepared_agent_request.prepared_messages_after_compaction
                ],
                request_json=prepared_payload,
                metadata=metadata,
                session=session_runtime,
                agent_settings=agent_settings,
                todo_state=prepared_agent_request.todo_state,
                prepared_auto_compaction=prepared_agent_request.prepared_auto_compaction,
                request_source=REQUEST_SOURCE_AUTOMATION,
            )
        except TaskCancelledError as exception:
            await finalize_automation_turn_cancelled(
                api_dependencies,
                runtime=runtime,
                session_runtime=session_runtime,
                turn_context=turn_context,
                session=session,
                exception=exception,
                message=str(exception.reason or "Chat stream was cancelled."),
            )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await cancel_automation_turn_streaming_task_noncritical(
                api_dependencies,
                runtime,
                turn_context,
                session,
                exception,
            )
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_EXECUTE,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Automation turn execution failed.",
                operation=OPERATION_EXECUTE,
                details={"automation_id": automation_id, "run_id": run_id},
            )
            if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
                await finalize_assistant_timeline_error(
                    session_runtime,
                    message=coerced.message,
                    code=str(coerced.code),
                )
            raise
        except asyncio.CancelledError as exception:
            await finalize_automation_turn_cancelled(
                api_dependencies,
                runtime=runtime,
                session_runtime=session_runtime,
                turn_context=turn_context,
                session=session,
                exception=exception,
                message="Chat stream was cancelled.",
            )
            raise
        finally:
            await session_runtime.close()
    finally:
        await release_automation_stream_runtime(api_dependencies, runtime)
    assistant_text = runtime.assistant_visible_text
    await commit_turn_assistant_message(
        api_dependencies,
        session,
        assistant_at_ms=runtime.assistant_at_ms,
    )
    return assistant_text
