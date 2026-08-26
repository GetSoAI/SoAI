"""SoAI - Modality usage extraction for orchestrator results [backend/orchestrator/execution/modality_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.metrics.usage import USAGE_METADATA_AUDIO_INPUT_BYTES, ModalityUsageRecord
from core.tasks.type_catalog import (
    TASK_TYPE_AUDIO_TRANSCRIPTION,
    TASK_TYPE_AUDIO_TRANSLATION,
    TASK_TYPE_IMAGE_EDIT,
    TASK_TYPE_IMAGE_GENERATION,
    TASK_TYPE_IMAGE_VARIATION,
    TaskTypeId,
)
from core.validation.strict_numbers import (
    coerce_non_negative_float_strict_or_zero,
    coerce_non_negative_int_strict_or_zero,
)
from orchestrator.execution.billing import resolve_usage_record_identity

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "record_binary_audio_modality_usage",
    "record_result_modality_usage",
)


def record_result_modality_usage(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    prompt_token_counter: PromptTokenCounter,
    task: Task,
    model_info: JSONDict,
    payload: JSONDict,
) -> None:
    if task.task_type in (TASK_TYPE_AUDIO_TRANSCRIPTION, TASK_TYPE_AUDIO_TRANSLATION):
        _record_audio_upload_usage(
            queue=queue,
            metrics=metrics,
            prompt_token_counter=prompt_token_counter,
            task=task,
            model_info=model_info,
            payload=payload,
        )
        return
    if task.task_type in (
        TASK_TYPE_IMAGE_GENERATION,
        TASK_TYPE_IMAGE_EDIT,
        TASK_TYPE_IMAGE_VARIATION,
    ):
        _record_image_usage(
            queue=queue,
            metrics=metrics,
            task=task,
            model_info=model_info,
            payload=payload,
        )


def record_binary_audio_modality_usage(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    prompt_token_counter: PromptTokenCounter,
    task: Task,
    model_info: JSONDict,
    audio_output_bytes: int,
    audio_output_seconds: float | None,
) -> None:
    context = queue.require_orchestration_context(task)
    request_payload = context.event.payload if context.event is not None else {}
    input_text = request_payload.get("input")
    text_tokens = _count_text_tokens(
        prompt_token_counter,
        model_info=model_info,
        value=input_text if isinstance(input_text, str) else None,
    )
    _record_usage(
        queue=queue,
        metrics=metrics,
        task=task,
        model_info=model_info,
        text_tokens=text_tokens,
        audio_output_bytes=max(0, int(audio_output_bytes)),
        audio_output_seconds=audio_output_seconds if audio_output_seconds is not None else 0.0,
    )


def _record_audio_upload_usage(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    prompt_token_counter: PromptTokenCounter,
    task: Task,
    model_info: JSONDict,
    payload: JSONDict,
) -> None:
    context = queue.require_orchestration_context(task)
    usage_metadata = context.event.usage_metadata if context.event is not None else {}
    transcript_text = _extract_transcript_text(payload)
    _record_usage(
        queue=queue,
        metrics=metrics,
        task=task,
        model_info=model_info,
        text_tokens=_count_text_tokens(
            prompt_token_counter,
            model_info=model_info,
            value=transcript_text,
        ),
        audio_input_bytes=coerce_non_negative_int_strict_or_zero(
            usage_metadata.get(USAGE_METADATA_AUDIO_INPUT_BYTES),
        ),
        audio_input_seconds=_extract_audio_input_seconds(payload),
    )


def _record_image_usage(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    task: Task,
    model_info: JSONDict,
    payload: JSONDict,
) -> None:
    context = queue.require_orchestration_context(task)
    request_payload = context.event.payload if context.event is not None else {}
    _record_usage(
        queue=queue,
        metrics=metrics,
        task=task,
        model_info=model_info,
        image_input_count=_count_image_inputs(task.task_type, request_payload),
        image_output_count=_count_image_outputs(payload),
    )


def _record_usage(
    *,
    queue: OrchestratorQueueProtocol,
    metrics: MetricsManagerProtocol,
    task: Task,
    model_info: JSONDict,
    text_tokens: int = 0,
    audio_input_bytes: int = 0,
    audio_input_seconds: float = 0.0,
    audio_output_bytes: int = 0,
    audio_output_seconds: float = 0.0,
    image_input_count: int = 0,
    image_output_count: int = 0,
) -> None:
    identity = resolve_usage_record_identity(
        queue=queue,
        task=task,
        model_info=model_info,
        missing_prefix="Modality usage",
    )
    if identity is None:
        return
    record = ModalityUsageRecord(
        plugin=identity.plugin_name,
        model_id=identity.model_id,
        client_id=identity.client_id,
        text_tokens=max(0, int(text_tokens)),
        audio_input_bytes=max(0, int(audio_input_bytes)),
        audio_input_seconds=_bound_seconds(audio_input_seconds),
        audio_output_bytes=max(0, int(audio_output_bytes)),
        audio_output_seconds=_bound_seconds(audio_output_seconds),
        image_input_count=max(0, int(image_input_count)),
        image_output_count=max(0, int(image_output_count)),
    )
    if record.has_usage():
        metrics.record_modality_usage(record)


def _extract_transcript_text(payload: JSONDict) -> str | None:
    text_value = payload.get("text")
    return text_value if isinstance(text_value, str) and text_value else None


def _extract_audio_input_seconds(payload: JSONDict) -> float:
    duration_seconds = coerce_non_negative_float_strict_or_zero(payload.get("duration"))
    if duration_seconds > 0.0:
        return duration_seconds
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return 0.0
    usage_type = usage.get("type")
    if usage_type != "duration":
        return 0.0
    return coerce_non_negative_float_strict_or_zero(usage.get("seconds"))


def _count_text_tokens(
    prompt_token_counter: PromptTokenCounter,
    *,
    model_info: JSONDict,
    value: str | None,
) -> int:
    if value is None:
        return 0
    model_value = model_info.get("model_id")
    model_name = model_value if isinstance(model_value, str) and model_value else None
    return prompt_token_counter.count_text_tokens(value, model_name=model_name)


def _count_image_inputs(task_type: TaskTypeId, request_payload: JSONDict) -> int:
    if task_type == TASK_TYPE_IMAGE_EDIT:
        paths = request_payload.get("image_temp_paths")
        if isinstance(paths, list | tuple):
            return len(paths)
        images = request_payload.get("images")
        return len(images) if isinstance(images, list) else 0
    if task_type == TASK_TYPE_IMAGE_VARIATION:
        path = request_payload.get("image_temp_path")
        return 1 if isinstance(path, str) and path else 0
    return 0


def _count_image_outputs(payload: JSONDict) -> int:
    data_value = payload.get("data")
    if isinstance(data_value, list):
        return len(data_value)
    images_value = payload.get("images")
    if isinstance(images_value, list):
        return len(images_value)
    return 0


def _bound_seconds(value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0.0:
        return 0.0
    return resolved
