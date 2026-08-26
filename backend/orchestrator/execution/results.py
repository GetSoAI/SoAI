"""SoAI - Result processing for orchestrator execution [backend/orchestrator/execution/results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import replace
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float
from core.metrics.protocols import MetricsManagerProtocol
from core.models.source_identifier import resolve_source_model_id
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.orchestration_context_cache import update_orchestration_context_from_current
from core.tasks.streaming_prefill_timeout import resolve_streaming_first_chunk_timeout
from core.tasks.task import Task
from core.tasks.type_catalog import (
    TASK_TYPE_AUDIO_TRANSCRIPTION,
    TASK_TYPE_IMAGE_EDIT,
    TASK_TYPE_IMAGE_GENERATION,
    TASK_TYPE_IMAGE_VARIATION,
    TASK_TYPE_TEXT_TO_SPEECH,
)
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from orchestrator.execution.dependencies import ResultProcessorDependencies
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.modality_usage import (
    record_binary_audio_modality_usage,
    record_result_modality_usage,
)
from orchestrator.execution.result_usage import finalize_usage_and_bill
from orchestrator.execution.stream_buffering import buffer_stream_to_result_payload
from orchestrator.execution.streaming import (
    STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT,
    STREAMING_CHUNK_DELIVERY_TIMEOUT_MINIMUM,
    STREAMING_IDLE_TIMEOUT_MINIMUM,
)
from orchestrator.execution.streaming_binary_result import handle_streaming_binary
from orchestrator.execution.streaming_completion import StreamingCompletion
from orchestrator.execution.streaming_result_handling import (
    handle_streaming_lightweight,
    handle_streaming_with_usage_parsing,
    should_parse_streaming_usage,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = ("ResultProcessor",)


class ResultProcessor:
    def __init__(self, deps: ResultProcessorDependencies) -> None:
        self._queue: OrchestratorQueueProtocol = deps.queue
        self._active_inferences: ActiveInferenceRegistryProtocol = deps.active_inferences
        self._health_check_config: JSONDict = deps.health_check_config
        self._metrics: MetricsManagerProtocol = deps.metrics
        self._temp_directory: str | None = deps.temp_directory
        self._prompt_token_counter = deps.prompt_token_counter

    def update_config(
        self,
        health_check_config: JSONDict,
        conservative_billing_threshold: float,
    ) -> None:
        _ = conservative_billing_threshold
        self._health_check_config = health_check_config

    def handle_unary_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: JSONDict,
        *,
        record_completion_delivery: bool = True,
        plugin_name: str = "",
    ) -> JSONDict:
        payload: JSONDict = dict(result)
        return finalize_usage_and_bill(
            task,
            model_info,
            payload,
            queue=self._queue,
            metrics=self._metrics,
            prompt_token_counter=self._prompt_token_counter,
            record_completion_delivery=record_completion_delivery,
            plugin_name=plugin_name,
        )

    async def handle_streaming_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: AsyncIterable[StreamChunk],
        *,
        usage_reporting_requested: bool,
        plugin_name: str = "",
    ) -> StreamingCompletion | JSONDict | None:
        context = self._queue.require_orchestration_context(task)
        if not context.streaming_started:
            updated_task = await update_orchestration_context_from_current(
                self._queue.task_registry,
                task.task_id,
                lambda current_context: replace(current_context, streaming_started=True),
            )
            if updated_task is None or updated_task.status.is_terminal():
                return None
            task = updated_task
            context = self._queue.require_orchestration_context(task)
        streaming_chunk_delivery_timeout = coerce_positive_float(
            self._health_check_config.get(
                "STREAMING_CHUNK_DELIVERY_TIMEOUT_SEC",
                STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT,
            ),
            default=STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT,
            minimum=STREAMING_CHUNK_DELIVERY_TIMEOUT_MINIMUM,
        )
        first_chunk_timeout = resolve_streaming_first_chunk_timeout(
            task=task,
            health_check_config=self._health_check_config,
        )
        streaming_idle_timeout = coerce_positive_float(
            self._health_check_config.get(
                "STREAMING_IDLE_TIMEOUT_SEC",
                LONG_REQUEST_TIMEOUT_SEC,
            ),
            default=LONG_REQUEST_TIMEOUT_SEC,
            minimum=STREAMING_IDLE_TIMEOUT_MINIMUM,
        )
        if task.task_type == TASK_TYPE_TEXT_TO_SPEECH:
            binary_result = await handle_streaming_binary(
                queue=self._queue,
                active_inferences=self._active_inferences,
                task=task,
                result=result,
                tracking_id=context.tracking_id,
                streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                first_chunk_timeout=first_chunk_timeout,
                streaming_idle_timeout=streaming_idle_timeout,
                temp_directory=self._temp_directory,
                dedup_hash=context.dedup_hash,
            )
            record_binary_audio_modality_usage(
                queue=self._queue,
                metrics=self._metrics,
                prompt_token_counter=self._prompt_token_counter,
                task=task,
                model_info=model_info,
                audio_output_bytes=binary_result.output_bytes,
                audio_output_seconds=binary_result.output_duration_seconds,
            )
            return (
                StreamingCompletion(
                    binary_replay_temp_path=binary_result.replay_temp_path,
                    chunk_delivery_timeout_seconds=streaming_chunk_delivery_timeout,
                )
                if binary_result.replay_temp_path is not None
                else None
            )
        if should_parse_streaming_usage(
            task=task,
            usage_reporting_requested=usage_reporting_requested,
        ):
            streaming_completion = await handle_streaming_with_usage_parsing(
                queue=self._queue,
                active_inferences=self._active_inferences,
                prompt_token_counter=self._prompt_token_counter,
                metrics=self._metrics,
                task=task,
                model_info=model_info,
                plugin_name=plugin_name,
                model_name=resolve_source_model_id(model_info),
                result=result,
                tracking_id=context.tracking_id,
                streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                first_chunk_timeout=first_chunk_timeout,
                streaming_idle_timeout=streaming_idle_timeout,
            )
            self._record_streaming_result_modality_usage(task, model_info, streaming_completion)
            return streaming_completion
        streaming_completion = await handle_streaming_lightweight(
            queue=self._queue,
            active_inferences=self._active_inferences,
            task=task,
            result=result,
            tracking_id=context.tracking_id,
            streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
            first_chunk_timeout=first_chunk_timeout,
            streaming_idle_timeout=streaming_idle_timeout,
            prompt_token_counter=self._prompt_token_counter,
            metrics=self._metrics,
            plugin_name=plugin_name,
            model_name=resolve_source_model_id(model_info),
        )
        self._record_streaming_result_modality_usage(task, model_info, streaming_completion)
        return streaming_completion

    async def buffer_stream_to_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: AsyncIterable[StreamChunk],
        *,
        plugin_name: str = "",
    ) -> JSONDict:
        result_payload = await buffer_stream_to_result_payload(
            queue=self._queue,
            active_inferences=self._active_inferences,
            task=task,
            result=result,
            health_check_config=self._health_check_config,
            metrics=self._metrics,
            prompt_token_counter=self._prompt_token_counter,
            plugin_name=plugin_name,
            model_name=resolve_source_model_id(model_info),
        )
        return self.handle_unary_result(
            task,
            model_info,
            result_payload,
            record_completion_delivery=False,
            plugin_name=plugin_name,
        )

    def _record_streaming_result_modality_usage(
        self,
        task: Task,
        model_info: JSONDict,
        streaming_completion: StreamingCompletion,
    ) -> None:
        if task.task_type not in (
            TASK_TYPE_AUDIO_TRANSCRIPTION,
            TASK_TYPE_IMAGE_GENERATION,
            TASK_TYPE_IMAGE_EDIT,
            TASK_TYPE_IMAGE_VARIATION,
        ):
            return
        if streaming_completion.final_result is None:
            return
        record_result_modality_usage(
            queue=self._queue,
            metrics=self._metrics,
            prompt_token_counter=self._prompt_token_counter,
            task=task,
            model_info=model_info,
            payload=streaming_completion.final_result,
        )
