"""SoAI - Tool-call execution input preparation [backend/orchestrator/tool_calls/execution_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.tool_call_arguments import normalize_openai_tool_call_arguments
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.storage_identity import build_tool_call_storage_id_from_fields
from orchestrator.tool_calls.execution_chronology import (
    resolve_tool_call_execution_chronology,
)
from orchestrator.tool_calls.persistence import ToolCallChronology

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PreparedToolCallExecutionInput",
    "prepare_tool_call_execution_input",
)


@dataclass(frozen=True, slots=True)
class PreparedToolCallExecutionInput:
    storage_call_identifier: str
    call_identifier: str
    tool_name: str
    arguments_payload: JSONDict | None
    arguments_json: str
    arguments_error: str | None
    chronology: ToolCallChronology


def prepare_tool_call_execution_input(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
) -> PreparedToolCallExecutionInput:
    call_identifier = str(tool_call.get("id") or "").strip() or f"call_{uuid.uuid4().hex}"
    storage_call_identifier = build_tool_call_storage_id_from_fields(
        conv_id=tool_context.conv_id,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
        assistant_turn_at_ms=tool_context.assistant_turn_at_ms,
        model_variant_index=tool_context.model_variant_index,
        message_index=tool_context.message_index,
        call_id=call_identifier,
    )
    tool_name = str(tool_call.get("name") or "").strip()
    arguments_payload, arguments_json, arguments_error = normalize_openai_tool_call_arguments(
        tool_call.get("arguments"),
    )
    return PreparedToolCallExecutionInput(
        storage_call_identifier=storage_call_identifier,
        call_identifier=call_identifier,
        tool_name=tool_name,
        arguments_payload=arguments_payload,
        arguments_json=arguments_json,
        arguments_error=arguments_error,
        chronology=resolve_tool_call_execution_chronology(tool_call),
    )
