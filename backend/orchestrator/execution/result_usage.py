"""SoAI - Usage normalization and billing helpers for result processing [backend/orchestrator/execution/result_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from orchestrator.execution.billing import apply_prompt_tokens, perform_billing_record
from orchestrator.execution.modality_usage import record_result_modality_usage

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("finalize_usage_and_bill",)


def finalize_usage_and_bill(
    task: Task,
    model_info: JSONDict,
    payload: JSONDict,
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    prompt_token_counter: PromptTokenCounter,
    record_completion_delivery: bool,
    plugin_name: str = "",
) -> JSONDict:
    usage_value = coerce_json_dict(payload.get("usage"))
    if usage_value is not None:
        payload["usage"] = apply_prompt_tokens(task, usage_value)
    usage_obj = payload.get("usage")
    completion_tokens_value = (
        usage_obj.get("completion_tokens", 0) if isinstance(usage_obj, dict) else 0
    )
    completion_tokens = completion_tokens_value if is_strict_int(completion_tokens_value) else 0
    total_tokens_value = usage_obj.get("total_tokens", 0) if isinstance(usage_obj, dict) else 0
    total_tokens = total_tokens_value if is_strict_int(total_tokens_value) else 0
    if total_tokens > 0:
        perform_billing_record(
            queue=queue,
            metrics=metrics,
            task=task,
            model_info=model_info,
            tokens=total_tokens,
            plugin_name=plugin_name,
        )
    if record_completion_delivery and plugin_name and completion_tokens > 0:
        metrics.record_completion_tokens(
            plugin_name,
            completion_tokens,
        )
    record_result_modality_usage(
        queue=queue,
        metrics=metrics,
        prompt_token_counter=prompt_token_counter,
        task=task,
        model_info=model_info,
        payload=payload,
    )
    return payload
