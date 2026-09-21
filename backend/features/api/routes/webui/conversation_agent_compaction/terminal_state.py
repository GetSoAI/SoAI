"""SoAI - Manual compaction terminal state normalization [backend/features/api/routes/webui/conversation_agent_compaction/terminal_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.context_compaction_result import (
    build_context_compaction_result_payload,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
    is_failure_tool_call_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ManualCompactionTerminalOutcome",
    "build_manual_compaction_terminal_outcome",
    "normalize_manual_compaction_terminal_status",
)

MANUAL_COMPACTION_CANCELLED_MESSAGE = "Manual compaction was cancelled."
MANUAL_COMPACTION_FAILED_MESSAGE = "Manual compaction failed."


@dataclass(frozen=True, slots=True)
class ManualCompactionTerminalOutcome:
    status: str
    result_payload: JSONValue
    error_message: str | None


def normalize_manual_compaction_terminal_status(status: str) -> str:
    normalized_status = str(status).strip()
    if normalized_status not in {
        TOOL_CALL_STATUS_COMPLETED,
        TOOL_CALL_STATUS_ERROR,
        TOOL_CALL_STATUS_CANCELLED,
    }:
        raise ValidationError("Manual compaction terminal status is invalid.")
    return normalized_status


def build_manual_compaction_terminal_outcome(
    *,
    status: str,
    result_text: str,
    prompt_message: JSONDict | None,
    error_message: str | None,
    result_details: JSONDict | None,
) -> ManualCompactionTerminalOutcome:
    normalized_status = normalize_manual_compaction_terminal_status(status)
    normalized_error_message = (
        str(error_message).strip()
        if isinstance(error_message, str) and error_message.strip()
        else None
    )
    if normalized_error_message is None and is_failure_tool_call_status(normalized_status):
        normalized_error_message = (
            MANUAL_COMPACTION_CANCELLED_MESSAGE
            if normalized_status == TOOL_CALL_STATUS_CANCELLED
            else MANUAL_COMPACTION_FAILED_MESSAGE
        )
    compaction_details = dict(result_details) if result_details is not None else {}
    compaction_details["trigger"] = "manual"
    result_payload: JSONValue = build_context_compaction_result_payload(
        status=normalized_status,
        output_text=str(result_text or ""),
        prompt_message=prompt_message,
        error_message=normalized_error_message,
        compaction_details=compaction_details,
        default_error_message=MANUAL_COMPACTION_FAILED_MESSAGE,
    )
    return ManualCompactionTerminalOutcome(
        status=normalized_status,
        result_payload=result_payload,
        error_message=normalized_error_message,
    )
