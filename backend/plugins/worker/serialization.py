"""SoAI - Plugin worker JSON serialization helpers [backend/plugins/worker/serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.models.model_context import ModelContext
from core.plugins.protocols_instance import ModelContextProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from core.validation.record_fields import (
    require_json_object,
    require_optional_json_object,
)
from plugins.worker.payload_fields import (
    read_bool_field,
    read_non_empty_raw_str_field,
    read_number_field,
    read_optional_int_field,
    read_optional_str_field,
    read_required_int_field,
)

__all__ = (
    "decode_model_context",
    "decode_request_context",
    "encode_model_context",
    "encode_request_context",
)

SERIALIZED_CONTEXT_FIELD_LABEL = "Serialized request context field"


def encode_request_context(context: RequestContext) -> JSONDict:
    return {
        "trace_id": context.trace_id,
        "client_ip": context.client_ip,
        "user_id": context.user_id,
        "timestamp": context.timestamp,
        "task_id": context.task_id,
        "cancellation_id": context.cancellation_id,
        "interactive_tool_approval": context.interactive_tool_approval,
        "agent_mode": context.agent_mode,
        "agent_turn_id": context.agent_turn_id,
        "agent_turn_scope": context.agent_turn_scope,
        "agent_turn_execution_token": context.agent_turn_execution_token,
        "agent_iteration_index": context.agent_iteration_index,
        "agent_parent_turn_id": context.agent_parent_turn_id,
        "agent_parent_tool_call_id": context.agent_parent_tool_call_id,
        "agent_parent_iteration_index": context.agent_parent_iteration_index,
        "agent_display_name": context.agent_display_name,
        "agent_requested_model": context.agent_requested_model,
        "agent_owner_task_id": context.agent_owner_task_id,
        "agent_workspace_path": context.agent_workspace_path,
    }


def decode_request_context(payload: JSONDict) -> RequestContext:
    return RequestContext(
        trace_id=read_non_empty_raw_str_field(
            payload,
            "trace_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        client_ip=read_optional_str_field(
            payload,
            "client_ip",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        user_id=read_required_int_field(payload, "user_id", label=SERIALIZED_CONTEXT_FIELD_LABEL),
        timestamp=float(
            read_number_field(payload, "timestamp", label=SERIALIZED_CONTEXT_FIELD_LABEL),
        ),
        task_id=read_optional_str_field(
            payload,
            "task_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        cancellation_id=read_non_empty_raw_str_field(
            payload,
            "cancellation_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        interactive_tool_approval=read_bool_field(
            payload,
            "interactive_tool_approval",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_mode=read_optional_str_field(
            payload,
            "agent_mode",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_turn_id=read_optional_str_field(
            payload,
            "agent_turn_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_turn_scope=read_optional_str_field(
            payload,
            "agent_turn_scope",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_turn_execution_token=read_optional_str_field(
            payload,
            "agent_turn_execution_token",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_iteration_index=read_optional_int_field(
            payload,
            "agent_iteration_index",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_parent_turn_id=read_optional_str_field(
            payload,
            "agent_parent_turn_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_parent_tool_call_id=read_optional_str_field(
            payload,
            "agent_parent_tool_call_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_parent_iteration_index=read_optional_int_field(
            payload,
            "agent_parent_iteration_index",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_display_name=read_optional_str_field(
            payload,
            "agent_display_name",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_requested_model=read_optional_str_field(
            payload,
            "agent_requested_model",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_owner_task_id=read_optional_str_field(
            payload,
            "agent_owner_task_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        agent_workspace_path=read_optional_str_field(
            payload,
            "agent_workspace_path",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
    )


def encode_model_context(context: ModelContextProtocol) -> JSONDict:
    return {
        "universal_id": context.universal_id,
        "source_model_id": context.source_model_id,
        "plugin": context.plugin,
        "model_path": context.model_path,
        "parameters": dict(context.parameters),
        "provider_details": context.provider_details,
    }


def decode_model_context(payload: JSONDict) -> ModelContext:
    parameters_value = payload.get("parameters")
    provider_details_value = payload.get("provider_details")
    parameters = require_json_object(
        parameters_value,
        label="Model context parameters",
        build_error=ValidationError,
        invalid_message="Model context parameters must be a JSON object.",
    )
    provider_details = require_optional_json_object(
        provider_details_value,
        label="Model context provider details",
        build_error=ValidationError,
        invalid_message="Model context provider details must be a JSON object.",
    )
    return ModelContext(
        universal_id=read_non_empty_raw_str_field(
            payload,
            "universal_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        source_model_id=read_non_empty_raw_str_field(
            payload,
            "source_model_id",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        plugin=read_non_empty_raw_str_field(
            payload,
            "plugin",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        model_path=read_optional_str_field(
            payload,
            "model_path",
            label=SERIALIZED_CONTEXT_FIELD_LABEL,
        ),
        parameters=parameters,
        provider_details=provider_details,
    )
