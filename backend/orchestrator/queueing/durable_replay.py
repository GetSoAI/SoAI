"""SoAI - Durable inference event replay helpers [backend/orchestrator/queueing/durable_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace

from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS
from core.errors.exceptions import StateError, ValidationError
from core.events.types_base import Event
from core.events.types_models_requests import (
    EmbeddingRequestReceived,
    ImageGenerationRequestReceived,
    InferenceRequestReceived,
    TextToSpeechRequestReceived,
)
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tasks.task import Task
from core.types.json import JSONValue, is_json_dict
from core.validation.integers import is_strict_int

__all__ = ("restore_durable_inference_event",)


def _resolve_event_class(event_type_name: str) -> type[InferenceRequestReceived]:
    if event_type_name == "EmbeddingRequestReceived":
        return EmbeddingRequestReceived
    if event_type_name == "ImageGenerationRequestReceived":
        return ImageGenerationRequestReceived
    if event_type_name == "TextToSpeechRequestReceived":
        return TextToSpeechRequestReceived
    if event_type_name == "InferenceRequestReceived":
        return InferenceRequestReceived
    raise ValidationError(f"Unsupported durable request event type '{event_type_name}'.")


def _build_tool_context(raw_value: JSONValue) -> MCPToolContext | None:
    if not is_json_dict(raw_value):
        return None
    conv_id_value = raw_value.get("conv_id")
    message_index_value = raw_value.get("message_index")
    user_id_value = raw_value.get("user_id")
    tool_map_value = raw_value.get("tool_map")
    if (
        not isinstance(conv_id_value, str)
        or not is_strict_int(message_index_value)
        or not is_strict_int(user_id_value)
        or not is_json_dict(tool_map_value)
    ):
        return None
    validated_tool_map: dict[str, dict[str, JSONValue]] = {}
    for tool_name, tool_value in tool_map_value.items():
        if not isinstance(tool_name, str) or not is_json_dict(tool_value):
            return None
        validated_tool_map[tool_name] = dict(tool_value)
    assistant_at_ms_value = raw_value.get("assistant_at_ms")
    assistant_at_ms = int(assistant_at_ms_value) if is_strict_int(assistant_at_ms_value) else None
    tool_approval_required_value = raw_value.get("tool_approval_required")
    tool_approval_required = (
        tool_approval_required_value if isinstance(tool_approval_required_value, bool) else False
    )
    assistant_turn_at_ms_value = raw_value.get("assistant_turn_at_ms")
    assistant_turn_at_ms = (
        int(assistant_turn_at_ms_value) if is_strict_int(assistant_turn_at_ms_value) else None
    )
    model_variant_index_value = raw_value.get("model_variant_index")
    model_variant_index = (
        int(model_variant_index_value) if is_strict_int(model_variant_index_value) else None
    )
    user_interaction_timeout_value = raw_value.get("user_interaction_timeout_ms")
    user_interaction_timeout_ms = (
        int(user_interaction_timeout_value)
        if is_strict_int(user_interaction_timeout_value) and user_interaction_timeout_value > 0
        else DEFAULT_USER_INTERACTION_TIMEOUT_MS
    )
    visible_tool_names_value = raw_value.get("visible_tool_names")
    visible_tool_names: tuple[str, ...] | None = None
    if isinstance(visible_tool_names_value, list):
        normalized_visible: list[str] = []
        for entry in visible_tool_names_value:
            if not isinstance(entry, str):
                return None
            normalized = entry.strip()
            if not normalized:
                continue
            normalized_visible.append(normalized)
        visible_tool_names = tuple(dict.fromkeys(normalized_visible))
    return MCPToolContext(
        conv_id=conv_id_value,
        message_index=message_index_value,
        user_id=user_id_value,
        tool_map=validated_tool_map,
        visible_tool_names=visible_tool_names,
        tool_approval_required=tool_approval_required,
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        user_interaction_timeout_ms=user_interaction_timeout_ms,
    )


def _build_request_context(task: Task) -> RequestContext:
    context = task.require_orchestration_context()
    payload = context.request_context_data
    trace_id_value = payload.get("trace_id")
    cancellation_id_value = payload.get("cancellation_id")
    if not isinstance(trace_id_value, str) or not trace_id_value:
        raise ValidationError("Persisted orchestration state is missing request_context.trace_id")
    if not isinstance(cancellation_id_value, str) or not cancellation_id_value:
        raise ValidationError(
            "Persisted orchestration state is missing request_context.cancellation_id",
        )
    client_ip_value = payload.get("client_ip")
    client_ip = client_ip_value if isinstance(client_ip_value, str) else None
    timestamp_value = payload.get("timestamp")
    timestamp = (
        float(timestamp_value)
        if (is_strict_int(timestamp_value) or isinstance(timestamp_value, float))
        else None
    )
    user_id_value = payload.get("user_id")
    user_id = int(user_id_value) if is_strict_int(user_id_value) else task.user_id
    agent_mode_value = payload.get("agent_mode")
    agent_mode = agent_mode_value if isinstance(agent_mode_value, str) else None
    agent_turn_id_value = payload.get("agent_turn_id")
    agent_turn_id = agent_turn_id_value if isinstance(agent_turn_id_value, str) else None
    execution_token_value = payload.get("agent_turn_execution_token")
    agent_turn_execution_token = (
        execution_token_value if isinstance(execution_token_value, str) else None
    )
    workspace_value = payload.get("agent_workspace_path")
    agent_workspace_path = workspace_value if isinstance(workspace_value, str) else None
    return RequestContext(
        trace_id=trace_id_value,
        client_ip=client_ip,
        user_id=user_id,
        timestamp=timestamp,
        task_id=task.task_id,
        cancellation_id=cancellation_id_value,
        mcp_tool_context=_build_tool_context(payload.get("mcp_tool_context")),
        agent_mode=agent_mode,
        agent_turn_id=agent_turn_id,
        agent_turn_execution_token=agent_turn_execution_token,
        agent_workspace_path=agent_workspace_path,
    )


def restore_durable_inference_event(task: Task) -> Task:
    context = task.require_orchestration_context()
    if context.event is not None:
        return task
    if not context.request_payload:
        raise StateError("Durable orchestration state is missing request payload.")
    request_context = _build_request_context(task)
    reply_queue = (
        task.reply_queue if task.reply_queue is not None else asyncio.Queue[Event](maxsize=1)
    )
    restored_event = _resolve_event_class(context.request_event_type)(
        context=request_context,
        payload=dict(context.request_payload),
        reply_channel=reply_queue,
        task_id=task.task_id,
        required_capabilities=tuple(context.required_capabilities),
        required_modalities=tuple(context.required_modalities),
    )
    return task.with_orchestration_context(replace(context, event=restored_event))
