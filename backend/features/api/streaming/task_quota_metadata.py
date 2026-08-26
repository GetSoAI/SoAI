"""SoAI - Task quota metadata normalization [backend/features/api/streaming/task_quota_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.openai.output_token_cap import OUTPUT_TOKEN_CAP_FIELDS
from core.quotas.token_reservation_payloads import (
    read_token_quota_prompt_tokens,
    resolve_token_quota_reservation,
)
from core.tasks.task import Task
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "read_task_quota_budget_inputs",
    "resolve_request_max_completion_tokens",
    "resolve_task_stream_model",
)


def read_task_quota_budget_inputs(
    task: Task,
) -> tuple[dict[str, JSONValue] | None, int | None, str | None]:
    metadata_value = task.metadata
    metadata: Mapping[str, JSONValue] = (
        metadata_value if isinstance(metadata_value, Mapping) else {}
    )
    quota_value = metadata.get("quota")
    quota_reservation = resolve_token_quota_reservation(quota_value)
    prompt_tokens = read_token_quota_prompt_tokens(metadata)
    model = coerce_optional_trimmed_str(metadata.get("model"))
    return (quota_reservation, prompt_tokens, model)


def resolve_task_stream_model(task: Task, explicit_model: str | None) -> str | None:
    normalized_explicit_model = coerce_optional_trimmed_str(explicit_model)
    if normalized_explicit_model is not None:
        return normalized_explicit_model
    _quota_reservation, _prompt_tokens, model_hint = read_task_quota_budget_inputs(task)
    return model_hint


def resolve_request_max_completion_tokens(
    request_payload: Mapping[str, JSONValue] | None,
) -> int | None:
    payload: Mapping[str, JSONValue] = (
        request_payload if isinstance(request_payload, Mapping) else {}
    )
    for key in OUTPUT_TOKEN_CAP_FIELDS:
        value = payload.get(key)
        if is_strict_int(value) and int(value) >= 0:
            return int(value)
    return None
