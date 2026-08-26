"""SoAI - Shared context compaction tool result payloads [backend/core/tool_calls/context_compaction_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.context_compaction_prompt_message import (
    normalize_context_compaction_prompt_message,
)
from core.tool_calls.status_values import (
    TOOL_CALL_FAILURE_STATUSES,
    TOOL_CALL_STATUS_COMPLETED,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_context_compaction_result_payload",)


def build_context_compaction_result_payload(
    *,
    status: str,
    output_text: str,
    prompt_message: JSONDict | None,
    error_message: str | None,
    compaction_details: JSONDict | None,
    default_error_message: str,
) -> JSONDict:
    result_payload: JSONDict = {"output": str(output_text or "")}
    normalized_prompt_message = normalize_context_compaction_prompt_message(prompt_message)
    if normalized_prompt_message is not None:
        result_payload["prompt_message"] = normalized_prompt_message
    if isinstance(compaction_details, dict) and compaction_details:
        result_payload["compaction"] = dict(compaction_details)
    if status in TOOL_CALL_FAILURE_STATUSES:
        result_payload["error"] = coerce_optional_trimmed_str(error_message) or str(
            default_error_message or "Context compaction failed.",
        )
    if status == TOOL_CALL_STATUS_COMPLETED:
        return result_payload
    if status in TOOL_CALL_FAILURE_STATUSES:
        return result_payload
    raise ValueError(f"Unsupported context compaction tool status: {status}")
