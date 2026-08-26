"""SoAI - Manual compaction run-state factory [backend/features/api/routes/webui/conversation_agent_compaction/run_state_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.webui.conversation_agent_compaction.execution_identity import (
    ManualCompactionExecutionIdentity,
)
from features.api.routes.webui.conversation_agent_compaction.run_state import (
    ManualCompactionRunState,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("build_manual_compaction_run_state",)


def build_manual_compaction_run_state(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    identity: ManualCompactionExecutionIdentity,
    execution_token: str,
    turn_cancellation_id: str | None,
    model: str,
    context_window_tokens: int,
    compaction_limit: int | None,
    summarizer_budget: int,
    source_messages: list[JSONDict],
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> ManualCompactionRunState:
    return ManualCompactionRunState(
        api_context=api_context,
        logger=logger,
        tool_call_id=identity.tool_call_id,
        turn_id=identity.turn_id,
        conv_id=identity.conv_id,
        user_id=identity.user_id,
        tool_started_at_ms=identity.tool_started_at_ms,
        iteration_index=identity.iteration_index,
        execution_token=execution_token,
        turn_cancellation_id=turn_cancellation_id,
        model=model,
        context_window_tokens=context_window_tokens,
        compaction_limit=compaction_limit,
        summarizer_budget=summarizer_budget,
        source_messages=source_messages,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )
