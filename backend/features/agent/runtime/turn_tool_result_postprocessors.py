"""SoAI - Agent turn tool-result postprocessors [backend/features/agent/runtime/turn_tool_result_postprocessors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from features.agent.runtime.tool_call_execution_support import (
    AgentToolCallPostprocessContext,
    AgentToolCallPostprocessResult,
)

if TYPE_CHECKING:
    from core.agent.todo_state_models import AgentTurnTodoState
    from core.agent.turn_state_writer import TurnStateWriter
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import TurnPrimitives

__all__ = (
    "build_todo_state_prompt_payload",
    "build_turn_tool_result_postprocessor",
)


def build_todo_state_prompt_payload(todo_state: AgentTurnTodoState) -> JSONDict:
    return {
        "revision": int(todo_state.todo_revision),
        "updated_at_ms": todo_state.todo_updated_at_ms,
        "explanation": todo_state.todo_explanation,
        "todo": [dict(entry) for entry in todo_state.todo],
    }


def build_turn_tool_result_postprocessor(
    *,
    primitives: TurnPrimitives,
    turn_state_writer: TurnStateWriter,
    next_action_sequence: Callable[[], Awaitable[int]],
) -> Callable[[AgentToolCallPostprocessContext], Awaitable[AgentToolCallPostprocessResult]]:
    async def postprocess(
        context: AgentToolCallPostprocessContext,
    ) -> AgentToolCallPostprocessResult:
        _ = primitives
        _ = next_action_sequence
        if context.tool_name == "todo_write":
            revision_value = context.result_payload.get("revision")
            if not isinstance(revision_value, int):
                return AgentToolCallPostprocessResult(
                    result_payload=dict(context.result_payload),
                    code_diffs=context.code_diffs,
                )
            parsed_todo_value = context.result_payload.get("todo")
            parsed_todo = (
                [dict(entry) for entry in parsed_todo_value if isinstance(entry, dict)]
                if isinstance(parsed_todo_value, list)
                else []
            )
            explanation_value = context.result_payload.get("explanation")
            explanation = explanation_value if isinstance(explanation_value, str) else None
            updated_at_ms = context.result_payload.get("updated_at_ms")
            turn_state_writer.update_todo_state(
                todo=list(parsed_todo),
                explanation=explanation,
                revision=int(revision_value),
                updated_at_ms=(int(updated_at_ms) if isinstance(updated_at_ms, int) else None),
            )
            return AgentToolCallPostprocessResult(
                result_payload=dict(context.result_payload),
                code_diffs=context.code_diffs,
                todo_updated=True,
                todo_revision=int(revision_value),
                todo=list(parsed_todo),
                todo_explanation=explanation,
            )
        if context.tool_name == "plan_write":
            revision_value = context.result_payload.get("revision")
            if not isinstance(revision_value, int):
                return AgentToolCallPostprocessResult(
                    result_payload=dict(context.result_payload),
                    code_diffs=context.code_diffs,
                )
            title_value = context.result_payload.get("title")
            markdown_value = context.result_payload.get("markdown")
            title = title_value if isinstance(title_value, str) else None
            if markdown_value is not None and not isinstance(markdown_value, str):
                return AgentToolCallPostprocessResult(
                    result_payload=dict(context.result_payload),
                    code_diffs=context.code_diffs,
                )
            markdown = markdown_value if isinstance(markdown_value, str) else None
            return AgentToolCallPostprocessResult(
                result_payload=dict(context.result_payload),
                code_diffs=context.code_diffs,
                plan_updated=True,
                plan_revision=int(revision_value),
                plan_title=title,
                plan_markdown=markdown,
            )
        return AgentToolCallPostprocessResult(
            result_payload=dict(context.result_payload),
            code_diffs=context.code_diffs,
        )

    return postprocess
