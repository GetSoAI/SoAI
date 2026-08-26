"""SoAI - Context compaction metric extraction [backend/core/tool_calls/context_compaction_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.serialization.json_parsing import parse_json_value
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_TERMINAL_STATUSES,
)
from core.types.json_value import coerce_json_dict
from core.validation.integers import coerce_non_negative_exact_int_or_none

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "resolve_context_compaction_metric_tokens_saved",
    "resolve_context_compaction_tokens_saved_from_details",
)


def _coerce_result_payload(value: JSONValue) -> JSONDict | None:
    if isinstance(value, str):
        try:
            parsed = parse_json_value(value, field="context compaction metric result")
        except ValidationError:
            return None
        return coerce_json_dict(normalize_for_json(parsed))
    return coerce_json_dict(normalize_for_json(value))


def resolve_context_compaction_tokens_saved_from_details(
    status: str,
    details: Mapping[str, JSONValue] | None,
) -> int:
    if status != TOOL_CALL_STATUS_COMPLETED or details is None:
        return 0
    before_tokens = coerce_non_negative_exact_int_or_none(details.get("prompt_tokens_before"))
    after_tokens = coerce_non_negative_exact_int_or_none(details.get("prompt_tokens_after"))
    if before_tokens is None or after_tokens is None:
        return 0
    return max(before_tokens - after_tokens, 0)


def resolve_context_compaction_metric_tokens_saved(
    tool_payload: Mapping[str, JSONValue],
) -> int | None:
    tool_name_value = tool_payload.get("tool_name")
    tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
    if tool_name != CONTEXT_COMPACTION_TOOL_NAME:
        return None
    status_value = tool_payload.get("status")
    status = status_value.strip() if isinstance(status_value, str) else ""
    if status not in TOOL_CALL_TERMINAL_STATUSES:
        return None
    result_payload = _coerce_result_payload(tool_payload.get("result"))
    details = coerce_json_dict(result_payload.get("compaction")) if result_payload else None
    return resolve_context_compaction_tokens_saved_from_details(status, details)
