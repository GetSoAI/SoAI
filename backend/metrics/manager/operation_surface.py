"""SoAI - Metrics manager operation enqueueing surface [backend/metrics/manager/operation_surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.monotonic import monotonic_ms
from metrics.manager.operations import MetricsQueueFullThrottle, queue_metrics_operation

__all__ = (
    "begin_token_stream",
    "finish_token_stream",
    "increment_counter",
    "increment_genesis_request",
    "purge_plugin_metrics",
    "queue_op",
    "record_historical_metric",
    "record_modality_usage",
    "record_timing",
    "record_token_stream_delta",
    "record_completion_tokens",
    "record_tokens_for_billing",
    "record_unique",
    "set_gauge",
    "update_download_speed_metrics",
)

if TYPE_CHECKING:
    import asyncio

    from core.metrics.usage import ModalityUsageRecord
    from metrics.manager.internal_protocols import MetricsOperationSurfaceOwnerProtocol
    from metrics.manager.types import (
        MetricsWorkerArg,
        MetricsWorkerOptionValue,
        MetricsWorkerQueueItem,
    )


def queue_op(
    manager: MetricsOperationSurfaceOwnerProtocol,
    operation: str,
    *args: MetricsWorkerArg,
    **option_values: MetricsWorkerOptionValue,
) -> None:
    queue: asyncio.Queue[MetricsWorkerQueueItem] | None = manager.background_queue
    accepting = bool(manager.accepting_operations)
    throttle: MetricsQueueFullThrottle = manager.queue_full_throttle
    queue_metrics_operation(queue, accepting, operation, args, option_values, throttle)


def increment_counter(
    manager: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    value: int = 1,
) -> None:
    queue_op(manager, "increment_counter", *keys, value=value)


def set_gauge(
    manager: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    value: float,
) -> None:
    queue_op(manager, "set_gauge", *keys, value=value)


def record_timing(
    manager: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    duration_ms: float,
) -> None:
    queue_op(manager, "record_timing", *keys, duration_ms=duration_ms)


def record_historical_metric(
    manager: MetricsOperationSurfaceOwnerProtocol,
    metric_key: str,
    value: float,
    observed_at_ms: int | None = None,
) -> None:
    queue_op(
        manager,
        "record_historical_metric",
        metric_key,
        value,
        observed_at_ms=observed_at_ms,
    )


def record_unique(
    manager: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    item: MetricsWorkerArg,
) -> None:
    queue_op(manager, "record_unique", *keys, item=item)


def record_tokens_for_billing(
    manager: MetricsOperationSurfaceOwnerProtocol,
    plugin: str,
    model_id: str,
    client_id: str,
    tokens: int,
) -> None:
    queue_op(manager, "record_tokens_for_billing", plugin, model_id, client_id, tokens)


def record_completion_tokens(
    manager: MetricsOperationSurfaceOwnerProtocol,
    plugin: str,
    tokens: int,
) -> None:
    manager.token_rate_calculator.record_completion_tokens(
        plugin,
        tokens,
        int(monotonic_ms()),
    )


def begin_token_stream(
    manager: MetricsOperationSurfaceOwnerProtocol,
    stream_id: str,
    plugin: str,
) -> None:
    manager.token_rate_calculator.begin_stream(stream_id, plugin, int(monotonic_ms()))


def record_token_stream_delta(
    manager: MetricsOperationSurfaceOwnerProtocol,
    stream_id: str,
    plugin: str,
    token_delta: int,
) -> None:
    manager.token_rate_calculator.record_stream_delta(
        stream_id,
        plugin,
        token_delta,
        int(monotonic_ms()),
    )


def finish_token_stream(
    manager: MetricsOperationSurfaceOwnerProtocol,
    stream_id: str,
) -> None:
    manager.token_rate_calculator.finish_stream(stream_id, int(monotonic_ms()))


def record_modality_usage(
    manager: MetricsOperationSurfaceOwnerProtocol,
    record: ModalityUsageRecord,
) -> None:
    queue_op(
        manager,
        "record_modality_usage",
        record.plugin,
        record.model_id,
        record.client_id,
        record.text_tokens,
        record.audio_input_bytes,
        record.audio_input_seconds,
        record.audio_output_bytes,
        record.audio_output_seconds,
        record.image_input_count,
        record.image_output_count,
    )


def update_download_speed_metrics(
    manager: MetricsOperationSurfaceOwnerProtocol,
    bytes_per_second: float,
    source: str = "real_download",
) -> None:
    queue_op(manager, "update_download_speed_metrics", bytes_per_second, source=source)


def increment_genesis_request(manager: MetricsOperationSurfaceOwnerProtocol) -> None:
    queue_op(manager, "increment_genesis_request")


def purge_plugin_metrics(manager: MetricsOperationSurfaceOwnerProtocol, plugin_name: str) -> None:
    normalized_name = plugin_name.strip()
    if not normalized_name:
        return
    queue_op(manager, "purge_plugin_metrics", normalized_name)
