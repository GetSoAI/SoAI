"""SoAI - MCP storage embedding generation and validation logic [backend/mcp/storage/embeddings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.error_types import ErrorType
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_plugins import ErrorEvent
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext, create_system_context
from core.runtime.request_sources import REQUEST_SOURCE_OPENAI
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_EMBEDDING
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.types.json_value import require_json_dict
from core.validation.requirements import require_float, require_int
from mcp.progress_reporting import publish_embedding_event
from mcp.storage.embedding_model_resolution import (
    resolve_embedding_model_for_embeddings_request,
)
from mcp.storage.internal_protocols import (
    EmbeddingCancellationChecker,
    EmbeddingProgressCallback,
    MCPStorageProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("generate_embeddings",)

LOGGER_NAME = "SoAI.mcp.storage.embeddings"
OPERATION = "mcp.storage.generate_embeddings"
EMBEDDING_RETRY_BASE_SECONDS = 2.0
EMBEDDING_RETRY_MAX_SECONDS = 30.0
RETRYABLE_EMBEDDING_ERROR_TYPES = frozenset(
    {
        ErrorType.TIMEOUT_ERROR,
        ErrorType.SERVICE_UNAVAILABLE,
        ErrorType.OVERLOADED,
        ErrorType.PLUGIN_UNAVAILABLE,
        ErrorType.PLUGIN_QUARANTINED,
        ErrorType.PLUGIN_INITIALIZING,
    },
)


async def _sleep_before_embedding_retry(attempt: int) -> None:
    delay_seconds = compute_exponential_backoff_seconds(
        attempt,
        base_seconds=EMBEDDING_RETRY_BASE_SECONDS,
        maximum_seconds=EMBEDDING_RETRY_MAX_SECONDS,
        jitter_ratio=0.2,
    )
    if delay_seconds > 0.0:
        await asyncio.sleep(delay_seconds)


def _is_retryable_embedding_error(event: ErrorEvent) -> bool:
    if event.error_type in RETRYABLE_EMBEDDING_ERROR_TYPES:
        return True
    normalized_message = event.message.strip().lower()
    return (
        "transient error" in normalized_message
        or "recovering" in normalized_message
        or "timed out" in normalized_message
    )


async def _create_embedding_task_and_publish(
    self: MCPStorageProtocol,
    payload: JSONDict,
    context: RequestContext,
    owner_id: str,
) -> asyncio.Queue[Event]:
    logger = get_logger(LOGGER_NAME)
    try:
        context_user_id = context.user_id
    except AttributeError:
        context_user_id = 0
    task, reply_queue = await create_streaming_task(
        self.task_registry,
        task_type=TASK_TYPE_EMBEDDING,
        user_id=int(context_user_id or 0),
        owner_id=owner_id,
        owner_type="system",
        cancellation_id=context.cancellation_id,
        initial_status=TaskStatus.QUEUED,
        metadata={
            "event_type": "rag_embedding_request",
            "model": payload.get("model"),
        },
        request_source=REQUEST_SOURCE_OPENAI,
        delivery_mode="blocking",
    )
    context.task_id = task.task_id
    await publish_embedding_event(
        event_bus=self.event_bus,
        task_registry=self.task_registry,
        context=context,
        payload=payload,
        reply_channel=reply_queue,
        task_id=task.task_id,
        required_capabilities=("embeddings",),
        logger=logger,
        operation="mcp.storage.create_embedding_task_and_publish",
        error_code=500,
        error_message="Failed to publish embedding event.",
        exception_types=RECOVERABLE_EXCEPTIONS,
    )
    return reply_queue


async def generate_embeddings(
    self: MCPStorageProtocol,
    texts: list[str],
    conv_id: str,
    user_id: int,
    embedding_model: str | None = None,
    task_id: str | None = None,
    out_actual_model: list[str] | None = None,
    token: CancellationTokenProtocol | None = None,
    send_progress: EmbeddingProgressCallback | None = None,
    check_cancellation: EmbeddingCancellationChecker | None = None,
) -> list[list[float]]:
    logger = get_logger(LOGGER_NAME)
    configured_batch_size = self.config.get_int("TOOLS.RAG.EMBEDDING_BATCH_SIZE")
    max_batch_chars = self.config.get_int("TOOLS.RAG.EMBEDDING_MAX_BATCH_CHARS")
    batch_size = max(1, configured_batch_size)
    max_batch_chars = max(1, max_batch_chars)
    resolved_request_model = embedding_model or "auto"
    resolved_request_model = await resolve_embedding_model_for_embeddings_request(
        self,
        resolved_request_model,
    )
    embedding_retry_attempts = max(1, self.config.get_int("TOOLS.RAG.EMBEDDING_RETRY_ATTEMPTS"))
    all_embeddings: list[list[float]] = []
    batch_ranges: list[tuple[int, int]] = []
    start_index = 0
    while start_index < len(texts):
        max_end_index = min(start_index + batch_size, len(texts))
        end_index = start_index
        current_chars = 0
        while end_index < max_end_index:
            next_size = len(texts[end_index])
            if end_index > start_index and current_chars + next_size > max_batch_chars:
                break
            current_chars += next_size
            end_index += 1
        if end_index == start_index:
            end_index = min(start_index + 1, len(texts))
        batch_ranges.append((start_index, end_index))
        start_index = end_index
    total_batches = len(batch_ranges)
    actual_model_used: str | None = None
    expected_dims: int | None = None
    for batch_num, batch_range in enumerate(batch_ranges):
        batch_start_index, batch_end_index = batch_range
        if task_id and check_cancellation:
            await check_cancellation(task_id, f"embedding-batch-{batch_num}", token=token)
        batch = texts[batch_start_index:batch_end_index]
        if task_id and send_progress:
            percent = 45 + int(batch_num / total_batches * 40) if total_batches > 0 else 85
            await send_progress(
                task_id,
                percent,
                f"Generating embeddings... (batch {batch_num + 1}/{total_batches})",
            )
        response: Event | None = None
        for attempt in range(embedding_retry_attempts):
            context = create_system_context(f"rag_embed_{conv_id}")
            context.user_id = 0 if isinstance(user_id, bool) else int(user_id or 0)
            reply_channel = await _create_embedding_task_and_publish(
                self,
                payload={"model": resolved_request_model, "input": batch},
                context=context,
                owner_id=f"rag_embed_{conv_id}",
            )
            try:
                response = await asyncio.wait_for(
                    reply_channel.get(),
                    timeout=self.embedding_timeout,
                )
            except TimeoutError as exception:
                logger.warning(
                    "Embedding request timed out after %ss for conversation %s",
                    self.embedding_timeout,
                    conv_id,
                )
                if attempt + 1 >= embedding_retry_attempts:
                    raise ValidationError(
                        f"Embedding request timed out after {self.embedding_timeout} seconds",
                    ) from exception
                await _sleep_before_embedding_retry(attempt)
                continue
            if not isinstance(response, ErrorEvent):
                break
            if attempt + 1 >= embedding_retry_attempts or not _is_retryable_embedding_error(
                response,
            ):
                break
            logger.warning(
                "Embedding request failed with retryable backend error for conversation %s: %s",
                conv_id,
                response.message,
            )
            await _sleep_before_embedding_retry(attempt)
        if response is None:
            raise ValidationError("Embedding request failed before receiving a response")
        if isinstance(response, ErrorEvent):
            raise ValidationError(f"Embedding request failed: {response.message}")
        if not isinstance(response, InferenceResultEvent):
            raise ValidationError(
                f"Invalid embedding response: missing payload (got {type(response).__name__})",
            )
        model_value = response.payload.get("model")
        actual_model_used = (
            model_value
            if isinstance(model_value, str) and model_value.strip()
            else resolved_request_model
        )
        data = response.payload.get("data")
        if not isinstance(data, list):
            raise ValidationError("Invalid embedding response: missing or invalid 'data' field")
        if not data:
            raise ValidationError("Invalid embedding response: 'data' is empty")
        if len(data) != len(batch):
            raise ValidationError(
                f"Embedding response size mismatch: got {len(data)}, expected {len(batch)}",
            )
        indexed_items: list[tuple[int, JSONDict]] = []
        indices: list[int] = []
        for raw_item in data:
            json_item = require_json_dict(raw_item, label="embedding.data.item")
            if "index" not in json_item:
                raise ValidationError("Embedding item missing 'index' field")
            item_index = require_int(json_item["index"], field="embedding.data.item.index")
            indices.append(item_index)
            indexed_items.append((item_index, json_item))
        if len(set(indices)) != len(indices):
            duplicates = [
                index_value for index_value in set(indices) if indices.count(index_value) > 1
            ]
            raise ValidationError(f"Duplicate embedding indices: {duplicates}")
        expected_set = set(range(len(batch)))
        if set(indices) != expected_set:
            missing = expected_set - set(indices)
            extra = set(indices) - expected_set
            raise ValidationError(
                f"Embedding indices {set(indices)} don't match expected {expected_set} (missing {missing}, extra {extra})",
            )
        indexed_items.sort(key=lambda item: item[0])
        for _, item in indexed_items:
            if "embedding" not in item:
                raise ValidationError("Invalid embedding response: item missing 'embedding' field")
            embedding_vector = item["embedding"]
            if not isinstance(embedding_vector, list) or not embedding_vector:
                raise ValidationError("Invalid embedding: must be non-empty list of numbers")
            numeric_embedding: list[float] = [
                require_float(value, field="embedding.value") for value in embedding_vector
            ]
            if expected_dims is None:
                expected_dims = len(numeric_embedding)
                if expected_dims <= 0:
                    raise ValidationError("Invalid embedding: zero-length vector")
            elif len(numeric_embedding) != expected_dims:
                raise ValidationError(
                    f"Embedding dimensions mismatch across batches: expected {expected_dims}, got {len(numeric_embedding)}",
                )
            all_embeddings.append(numeric_embedding)
    if len(all_embeddings) != len(texts):
        raise ValidationError(
            f"Embeddings count mismatch: got {len(all_embeddings)}, expected {len(texts)}",
        )
    if out_actual_model is not None and actual_model_used:
        out_actual_model.clear()
        out_actual_model.append(str(actual_model_used))
    return all_embeddings
