"""SoAI - Agent turn iteration policy retry messages [backend/features/agent/runtime/turn_iteration_policy_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_defaults import resolve_agent_turn_terminal_defaults
from core.agent.status_values import AGENT_TURN_STATUS_CANCELLED
from core.openai.internal_retry_prompt import build_internal_retry_user_message
from core.prompts.system_prompts import (
    get_required_visible_output_system_text_v1,
    get_text_prompt_v1,
    render_text_prompt_template_v1,
)
from core.types.json import JSONDict

__all__ = (
    "build_finish_reason_length_continue_message",
    "build_invalid_tool_call_json_final_answer_message",
    "build_invalid_tool_call_json_repair_message",
    "build_required_visible_output_message",
    "build_tool_call_protocol_final_answer_message",
    "build_tool_call_protocol_repair_message",
    "build_tool_call_protocol_strategy_message",
    "build_tool_sequence_contract_repair_message",
    "get_cancelled_status",
)


def get_cancelled_status() -> tuple[str, str, str]:
    status, error_message, error_type = resolve_agent_turn_terminal_defaults(
        AGENT_TURN_STATUS_CANCELLED,
    )
    return (
        status,
        error_message or "Agent turn cancelled.",
        error_type or AGENT_TURN_STATUS_CANCELLED,
    )


def build_required_visible_output_message() -> JSONDict:
    return build_internal_retry_user_message(get_required_visible_output_system_text_v1())


def build_finish_reason_length_continue_message() -> JSONDict:
    return build_internal_retry_user_message(
        get_text_prompt_v1("agent.turn_iteration.continue_finish_reason_length.v1"),
    )


def build_tool_sequence_contract_repair_message() -> JSONDict:
    return build_internal_retry_user_message(
        get_text_prompt_v1("agent.turn_iteration.repair_tool_sequence.v1"),
    )


def build_invalid_tool_call_json_repair_message() -> JSONDict:
    return build_internal_retry_user_message(
        get_text_prompt_v1("agent.turn_iteration.repair_invalid_tool_call_json.v1"),
    )


def build_invalid_tool_call_json_final_answer_message() -> JSONDict:
    return build_internal_retry_user_message(
        get_text_prompt_v1(
            "agent.turn_iteration.final_answer_without_tools_after_invalid_tool_call_json.v1",
        ),
    )


def build_tool_call_protocol_repair_message(
    *,
    tool_name: str,
    error_message: str,
    received_argument_type: str,
) -> JSONDict:
    return build_internal_retry_user_message(
        render_text_prompt_template_v1(
            "agent.turn_iteration.repair_tool_call_protocol.v1",
            {
                "TOOL_NAME": tool_name,
                "ERROR_MESSAGE": error_message,
                "RECEIVED_ARGUMENT_TYPE": received_argument_type,
            },
        ),
    )


def build_tool_call_protocol_strategy_message(
    *,
    tool_name: str,
    error_message: str,
    received_argument_type: str,
) -> JSONDict:
    return build_internal_retry_user_message(
        render_text_prompt_template_v1(
            "agent.turn_iteration.change_strategy_after_tool_call_protocol_failure.v1",
            {
                "TOOL_NAME": tool_name,
                "ERROR_MESSAGE": error_message,
                "RECEIVED_ARGUMENT_TYPE": received_argument_type,
            },
        ),
    )


def build_tool_call_protocol_final_answer_message(
    *,
    tool_name: str,
    error_message: str,
    received_argument_type: str,
) -> JSONDict:
    return build_internal_retry_user_message(
        render_text_prompt_template_v1(
            "agent.turn_iteration.final_answer_after_tool_call_protocol_failure.v1",
            {
                "TOOL_NAME": tool_name,
                "ERROR_MESSAGE": error_message,
                "RECEIVED_ARGUMENT_TYPE": received_argument_type,
            },
        ),
    )
