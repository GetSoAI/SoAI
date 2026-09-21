"""SoAI - SoAIBench terminal companion projection [backend/hardware/soaibench/terminal_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.tasks.enums import TaskStatus
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict_or_empty
from hardware.soaibench.responses import score_payload
from hardware.soaibench.types import SoAIBenchRunStatus

__all__ = ("SoAIBenchTerminalProjection", "terminal_projection")


@dataclass(frozen=True, slots=True)
class SoAIBenchTerminalProjection:
    task_status: TaskStatus
    task_result: JSONDict
    error_message: str | None
    status_message: str | None
    tool_status: str
    tool_error_message: str | None


def terminal_projection(run: JSONDict) -> SoAIBenchTerminalProjection:
    status = SoAIBenchRunStatus(str(run["status"]))
    result: JSONDict = {"run_id": str(run["run_id"]), "status": status.value}
    score = score_payload(run)
    if score is not None:
        result["score"] = score
    if status == SoAIBenchRunStatus.COMPLETED:
        return SoAIBenchTerminalProjection(
            task_status=TaskStatus.COMPLETED,
            task_result=result,
            error_message=None,
            status_message="SoAIBench completed.",
            tool_status=TOOL_CALL_STATUS_COMPLETED,
            tool_error_message=None,
        )
    if status in {SoAIBenchRunStatus.CANCELLED, SoAIBenchRunStatus.STOPPED}:
        message = (
            "SoAIBench stopped." if status == SoAIBenchRunStatus.STOPPED else "SoAIBench cancelled."
        )
        if run.get("failure_reason") is not None:
            failure_message = _terminal_error_message(run)
            return SoAIBenchTerminalProjection(
                task_status=TaskStatus.FAILED,
                task_result=result,
                error_message=failure_message,
                status_message=None,
                tool_status=TOOL_CALL_STATUS_ERROR,
                tool_error_message=failure_message,
            )
        return SoAIBenchTerminalProjection(
            task_status=TaskStatus.CANCELLED,
            task_result=result,
            error_message=None,
            status_message=message,
            tool_status=TOOL_CALL_STATUS_CANCELLED,
            tool_error_message=message,
        )
    message = _terminal_error_message(run)
    return SoAIBenchTerminalProjection(
        task_status=TaskStatus.FAILED,
        task_result=result,
        error_message=message,
        status_message=None,
        tool_status=TOOL_CALL_STATUS_ERROR,
        tool_error_message=message,
    )


def _terminal_error_message(run: JSONDict) -> str:
    summary = coerce_json_dict_or_empty(run.get("summary"))
    message = summary.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    for key in ("failure_reason", "unsupported_reason"):
        reason = run.get(key)
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    return "SoAIBench failed."
