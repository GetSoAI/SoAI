"""SoAI - Subagent stream execution [backend/features/agent/subagents/stream_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.errors.exceptions import StateError, ValidationError
from core.openai.token_accounting import (
    build_prompt_occupancy_metadata,
    count_prompt_occupancy_async,
)
from core.prompts.system_prompts import get_text_prompt_v1
from core.runtime.cancellation_ids import (
    build_agent_iteration_cancellation_id,
    build_agent_turn_cancellation_id,
)
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_SUBAGENT
from core.serialization.json import serialize_json_compact_stable_strict
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.types.json_value import coerce_json_dict
from features.agent.runtime.claimed_prepared_stream_execution import (
    execute_claimed_prepared_stream,
)
from features.agent.runtime.execution_preparation import (
    build_headless_agent_turn_engine_dependencies_from_api_dependencies,
)
from features.agent.runtime.execution_request_preparation import (
    build_prepared_execution_request,
)
from features.agent.runtime.openai_payload import coerce_usage_dict
from features.agent.runtime.streaming_inference_admission import (
    AgentStreamingTaskBundle,
)
from features.agent.subagents.token_usage import (
    build_actual_subagent_token_usage,
    read_subagent_prompt_token_metadata,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "SubagentStreamExecutionOutcome",
    "execute_subagent_stream",
)


@dataclass(frozen=True, slots=True)
class SubagentStreamExecutionOutcome:
    prompt_tokens: int
    prompt_tokens_capped: bool
    prompt_tokens_capped_reason: str | None
    prompt_tokens_precision: Literal["exact", "estimated"]
    final_token_usage: JSONDict | None
    reached_max_iterations: bool


async def execute_subagent_stream(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
    requested_model: str,
    settings: AgentSettings,
    execution_request: JSONDict,
    task_text: str,
    task_context: str | None,
    on_stream_initialized: Callable[
        [int, bool, str | None, Literal["exact", "estimated"]],
        Awaitable[None],
    ],
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None]],
    on_raw_bytes: Callable[[bytes], Awaitable[None]],
) -> SubagentStreamExecutionOutcome:
    deps = build_headless_agent_turn_engine_dependencies_from_api_dependencies(
        api_dependencies=api_dependencies,
        logger=logger,
    )
    prepared_request = await build_prepared_execution_request(
        prompt_token_counter=api_dependencies.prompt_token_counter,
        source_policy="inherited_subagent",
        request_json=execution_request,
        source_messages=[
            {
                "role": "user",
                "content": _build_subagent_user_message(task_text, task_context),
            },
        ],
        boundary_source_messages=[
            {
                "role": "user",
                "content": _build_subagent_user_message(task_text, task_context),
            },
        ],
        conv_id=subagent_tool_context.conv_id,
        user_id=subagent_tool_context.user_id,
        requested_model=requested_model,
        agent_settings=settings,
        todo_state=None,
        subagent_summaries=[],
        tool_context=subagent_tool_context,
        scope_message=_build_subagent_scope_system_message(subagent_context),
        prune_empty_messages=False,
        stream=True,
        summarize_messages=None,
    )
    payload = dict(prepared_request.final_payload)
    subagent_turn_cancellation_id = _build_subagent_turn_cancellation_id(
        subagent_context=subagent_context,
        mode=settings.mode,
    )
    first_iteration_cancellation_id = build_agent_iteration_cancellation_id(
        turn_cancellation_id=subagent_turn_cancellation_id,
        iteration_index=0,
        mode=settings.mode,
    )
    metadata: JSONDict = {
        "turn_scope": TURN_SCOPE_SUBAGENT,
        "agent_turn_id": str(subagent_context.agent_turn_id or "").strip(),
    }
    metadata.update(
        build_prompt_occupancy_metadata(
            await count_prompt_occupancy_async(
                prompt_token_counter=api_dependencies.prompt_token_counter,
                request_payload=payload,
                token_estimation_profile=settings.token_estimation_profile,
            ),
        ),
    )

    async def handle_initial_bundle(
        bundle: AgentStreamingTaskBundle,
    ) -> None:
        prompt_metadata = read_subagent_prompt_token_metadata(bundle.task.metadata)
        await on_stream_initialized(
            prompt_metadata.prompt_tokens,
            prompt_metadata.capped,
            prompt_metadata.capped_reason,
            prompt_metadata.precision,
        )

    execution = await execute_claimed_prepared_stream(
        api_dependencies,
        deps=deps,
        context=subagent_context,
        tool_context=subagent_tool_context,
        requested_model=requested_model,
        settings=settings,
        todo_state=None,
        initial_messages=_read_payload_messages(payload),
        initial_boundary_source_messages=prepared_request.boundary_source_messages,
        base_request_payload=payload,
        owner_id=subagent_tool_context.conv_id,
        cancellation_id=first_iteration_cancellation_id,
        metadata=metadata,
        request_source=REQUEST_SOURCE_SUBAGENT,
        on_bytes=on_raw_bytes,
        on_initial_bundle=handle_initial_bundle,
        on_visible_deltas=on_visible_deltas,
        on_inference_payload_prepared=None,
        on_compacted_prompt_occupancy=None,
        include_usage=False,
        include_usage_in_result=True,
        summarize_messages=None,
        prepared_auto_compaction=prepared_request.prepared_auto_compaction,
        turn_id=subagent_context.agent_turn_id,
        initial_active_inference_cancellation_id=first_iteration_cancellation_id,
        on_claimed=None,
        operation="agent.subagents.stream_execution.turn_cleanup",
        cancelled_log_message="Failed to finalize subagent turn after cancellation (non-critical).",
    )
    if execution.initial_bundle is None:
        raise StateError("Subagent execution completed without an initial inference task.")
    prompt_metadata = read_subagent_prompt_token_metadata(execution.initial_bundle.task.metadata)
    return SubagentStreamExecutionOutcome(
        prompt_tokens=prompt_metadata.prompt_tokens,
        prompt_tokens_capped=prompt_metadata.capped,
        prompt_tokens_capped_reason=prompt_metadata.capped_reason,
        prompt_tokens_precision=prompt_metadata.precision,
        final_token_usage=build_actual_subagent_token_usage(
            usage=coerce_usage_dict(coerce_json_dict(execution.result.final_payload.get("usage"))),
            prompt_tokens_capped=prompt_metadata.capped,
            prompt_tokens_capped_reason=prompt_metadata.capped_reason,
            prompt_tokens_precision=prompt_metadata.precision,
        ),
        reached_max_iterations=execution.result.reached_max_iterations,
    )


def _build_subagent_turn_cancellation_id(
    *,
    subagent_context: RequestContext,
    mode: str,
) -> str:
    base_cancellation_id = normalize_cancellation_id(subagent_context.cancellation_id)
    subagent_turn_id = str(subagent_context.agent_turn_id or "").strip()
    if not base_cancellation_id or not subagent_turn_id:
        raise ValidationError("Subagent background execution requires subagent cancellation state.")
    return build_agent_turn_cancellation_id(
        base_cancellation_id=base_cancellation_id,
        turn_id=subagent_turn_id,
        mode=mode,
    )


def _read_payload_messages(payload: JSONDict) -> list[JSONDict]:
    messages_value = payload.get("messages")
    if not isinstance(messages_value, list):
        raise ValidationError("Subagent request payload messages are invalid.")
    messages: list[JSONDict] = []
    for entry in messages_value:
        message = coerce_json_dict(entry)
        if message is None:
            raise ValidationError("Subagent request payload message is invalid.")
        messages.append(message)
    return messages


def _build_subagent_user_message(task_text: str, task_context: str | None) -> str:
    message = task_text.strip()
    if isinstance(task_context, str) and task_context.strip():
        return f"{message}\n\nAdditional context:\n{task_context.strip()}"
    return message


def _build_subagent_scope_system_message(
    subagent_context: RequestContext,
) -> JSONDict:
    payload = {
        "display_name": subagent_context.agent_display_name,
        "mode": subagent_context.agent_mode,
        "subagent_id": subagent_context.agent_turn_id,
        "parent_turn_id": subagent_context.agent_parent_turn_id,
        "parent_iteration_index": subagent_context.agent_parent_iteration_index,
        "instruction": get_text_prompt_v1("agent.subagent.scope_instruction.v1"),
    }
    return {
        "role": "system",
        "content": (
            "<agent_subagent_scope>"
            f"{serialize_json_compact_stable_strict(payload, ensure_ascii=False)}"
            "</agent_subagent_scope>"
        ),
    }
