"""SoAI - Manual compaction run-state helpers [backend/features/api/routes/webui/conversation_agent_compaction/run_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.types.json import JSONDict
from features.api.routes.webui.conversation_agent_compaction.finalization import (
    finalize_manual_compaction_failure,
    finalize_manual_compaction_success,
)
from features.api.routes.webui.conversation_agent_compaction.result_details import (
    resolve_manual_compaction_result_details,
)
from features.api.routes.webui.conversation_agent_compaction.summarizer_pipeline import (
    ManualCompactionSummaryResult,
)
from features.api.runtime.context import ApiContext

__all__ = ("ManualCompactionRunState",)


class ManualCompactionRunState:
    def __init__(
        self,
        *,
        api_context: ApiContext,
        logger: LoggerProtocol,
        conv_id: str,
        user_id: int,
        turn_id: str,
        iteration_index: int,
        tool_call_id: str,
        tool_started_at_ms: int,
        execution_token: str,
        turn_cancellation_id: str | None,
        model: str,
        context_window_tokens: int,
        compaction_limit: int | None,
        summarizer_budget: int,
        source_messages: list[JSONDict],
        replace_assistant_at_ms: int | None,
        replace_tool_call_id: str | None,
    ) -> None:
        self._api_context = api_context
        self._logger = logger
        self._conv_id = str(conv_id)
        self._user_id = int(user_id)
        self._turn_id = str(turn_id)
        self._iteration_index = int(iteration_index)
        self._tool_call_id = str(tool_call_id)
        self._tool_started_at_ms = int(tool_started_at_ms)
        self._execution_token = str(execution_token)
        self._turn_cancellation_id = turn_cancellation_id
        self._model = str(model)
        self._context_window_tokens = int(context_window_tokens)
        self._compaction_limit = compaction_limit
        self._summarizer_budget = int(summarizer_budget)
        self._source_messages = [dict(message) for message in source_messages]
        self._replace_assistant_at_ms = replace_assistant_at_ms
        self._replace_tool_call_id = replace_tool_call_id

    async def resolve_tool_result_details(
        self,
        summary: ManualCompactionSummaryResult | None,
    ) -> JSONDict:
        return await resolve_manual_compaction_result_details(
            api_context=self._api_context,
            logger=self._logger,
            conv_id=self._conv_id,
            user_id=self._user_id,
            model=self._model,
            context_window_tokens=self._context_window_tokens,
            compaction_limit=self._compaction_limit,
            summarizer_budget=self._summarizer_budget,
            source_messages=self._source_messages,
            summary=summary,
        )

    async def finalize_success(
        self,
        *,
        completed_at_ms: int,
        activity_output_text: str,
        activity_prompt_message: JSONDict | None,
        tool_result_details: JSONDict,
    ) -> None:
        await finalize_manual_compaction_success(
            api_context=self._api_context,
            logger=self._logger,
            conv_id=self._conv_id,
            user_id=self._user_id,
            turn_id=self._turn_id,
            iteration_index=self._iteration_index,
            tool_call_id=self._tool_call_id,
            tool_started_at_ms=self._tool_started_at_ms,
            execution_token=self._execution_token,
            turn_cancellation_id=self._turn_cancellation_id,
            completed_at_ms=int(completed_at_ms),
            model_id=self._model,
            assistant_at_ms=self._tool_started_at_ms,
            activity_output_text=str(activity_output_text or ""),
            activity_prompt_message=activity_prompt_message,
            tool_result_details=tool_result_details,
            replace_assistant_at_ms=self._replace_assistant_at_ms,
            replace_tool_call_id=self._replace_tool_call_id,
        )

    async def finalize_failure(
        self,
        *,
        completed_at_ms: int,
        failure_status: str,
        activity_output_text: str,
        activity_prompt_message: JSONDict | None,
        error_message: str,
        error_type: str,
        tool_result_details: JSONDict,
    ) -> None:
        await finalize_manual_compaction_failure(
            api_context=self._api_context,
            logger=self._logger,
            conv_id=self._conv_id,
            user_id=self._user_id,
            turn_id=self._turn_id,
            iteration_index=self._iteration_index,
            tool_call_id=self._tool_call_id,
            tool_started_at_ms=self._tool_started_at_ms,
            execution_token=self._execution_token,
            turn_cancellation_id=self._turn_cancellation_id,
            completed_at_ms=int(completed_at_ms),
            model_id=self._model,
            assistant_at_ms=self._tool_started_at_ms,
            failure_status=failure_status,
            activity_output_text=str(activity_output_text or ""),
            activity_prompt_message=activity_prompt_message,
            error_message=str(error_message or ""),
            error_type=str(error_type or ""),
            tool_result_details=tool_result_details,
            replace_assistant_at_ms=self._replace_assistant_at_ms,
            replace_tool_call_id=self._replace_tool_call_id,
        )
