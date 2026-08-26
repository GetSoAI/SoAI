"""SoAI - Outcome quota and token extraction helpers [backend/orchestrator/execution/outcome_quota_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.quotas.token_reservation_payloads import (
    resolve_token_quota_units_for_terminal_failure,
)
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "extract_quota_units_for_terminal_failure",
    "extract_total_tokens",
)


def extract_total_tokens(usage_payload: JSONDict | None) -> int:
    if usage_payload is None:
        return 0
    total_tokens_value = usage_payload.get("total_tokens")
    if is_strict_int(total_tokens_value) and total_tokens_value > 0:
        return int(total_tokens_value)
    prompt_tokens_value = usage_payload.get("prompt_tokens")
    completion_tokens_value = usage_payload.get("completion_tokens")
    if is_strict_int(prompt_tokens_value) and is_strict_int(completion_tokens_value):
        combined = int(prompt_tokens_value) + int(completion_tokens_value)
        if combined > 0:
            return combined
    if is_strict_int(completion_tokens_value) and completion_tokens_value > 0:
        return int(completion_tokens_value)
    if is_strict_int(prompt_tokens_value) and prompt_tokens_value > 0:
        return int(prompt_tokens_value)
    input_tokens_value = usage_payload.get("input_tokens")
    output_tokens_value = usage_payload.get("output_tokens")
    combined = 0
    if is_strict_int(input_tokens_value) and input_tokens_value > 0:
        combined += int(input_tokens_value)
    if is_strict_int(output_tokens_value) and output_tokens_value > 0:
        combined += int(output_tokens_value)
    return int(combined)


def extract_quota_units_for_terminal_failure(task: Task, reason: str) -> int:
    return resolve_token_quota_units_for_terminal_failure(task.metadata.get("quota"), reason=reason)
