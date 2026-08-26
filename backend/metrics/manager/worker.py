"""SoAI - Metrics background worker handlers [backend/metrics/manager/worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.metrics.usage import ModalityUsageRecord
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    coerce_non_negative_float_strict_or_zero,
    coerce_non_negative_int_strict_or_zero,
)
from metrics.manager.billing_usage_collectors import (
    record_modality_usage,
    record_tokens_for_billing,
)
from metrics.manager.collectors import (
    increment_counter,
    increment_genesis_request,
    record_timing,
    record_unique,
    set_gauge,
    update_download_speed,
)
from metrics.manager.configuration import MAX_BILLING_MODEL_CARDINALITY
from metrics.manager.internal_protocols import (
    DownloadSpeedDatabaseProtocol,
)
from metrics.manager.plugin_cleanup import purge_plugin_scoped_metrics
from metrics.manager.types import MetricsWorkerPayload
from metrics.manager.worker_payloads import (
    coerce_metric_keys,
    extract_options,
    get_float_arg,
    get_numeric_option,
    get_str_arg,
    get_strict_int_arg,
    get_unique_item_option,
)

if TYPE_CHECKING:
    from core.metrics.protocols import DatabaseMetricsProtocol
    from core.tasks.action_queue import ActionHandler
    from metrics.manager.types import MetricsTree

__all__ = ("create_worker_handlers",)


def create_worker_handlers(
    lock: asyncio.Lock,
    metrics_ref: list[MetricsTree],
    genesis_flush_lock: asyncio.Lock,
    genesis_requests_delta: list[int],
    genesis_tokens_delta: list[int],
    database_hardware: DownloadSpeedDatabaseProtocol,
    database_metrics: DatabaseMetricsProtocol,
    max_billing_client_cardinality: int,
) -> dict[str, ActionHandler[MetricsWorkerPayload]]:
    async def handle_increment_counter(_action: str, payload: MetricsWorkerPayload) -> None:
        keys = coerce_metric_keys(payload)
        option_values = extract_options(payload)
        value_obj = option_values.get("value", 1)
        value = int(value_obj) if is_strict_int(value_obj) else 1
        await increment_counter(lock, metrics_ref[0], keys, value)

    async def handle_set_gauge(_action: str, payload: MetricsWorkerPayload) -> None:
        keys = coerce_metric_keys(payload)
        value = get_numeric_option(payload, "value", 0)
        await set_gauge(lock, metrics_ref[0], keys, value)

    async def handle_record_timing(_action: str, payload: MetricsWorkerPayload) -> None:
        keys = coerce_metric_keys(payload)
        duration_ms = float(get_numeric_option(payload, "duration_ms", 0.0))
        await record_timing(lock, metrics_ref[0], keys, duration_ms)

    async def handle_record_historical_metric(_action: str, payload: MetricsWorkerPayload) -> None:
        metric_key = get_str_arg(payload, 0)
        value = get_float_arg(payload, 1)
        if metric_key is None or value is None:
            return
        observed_value = get_numeric_option(payload, "observed_at_ms", 0)
        observed_at_ms = int(observed_value) if observed_value > 0 else None
        await database_metrics.log_historical_metric(metric_key, value, observed_at_ms)

    async def handle_record_unique(_action: str, payload: MetricsWorkerPayload) -> None:
        keys = coerce_metric_keys(payload)
        item = get_unique_item_option(payload, "item")
        if item is None:
            return
        await record_unique(lock, metrics_ref[0], keys, item)

    async def handle_tokens(_action: str, payload: MetricsWorkerPayload) -> None:
        plugin = get_str_arg(payload, 0)
        model_id = get_str_arg(payload, 1)
        client_id = get_str_arg(payload, 2)
        tokens_value = get_strict_int_arg(payload, 3)
        if plugin is None or model_id is None or client_id is None or tokens_value is None:
            return
        await record_tokens_for_billing(
            lock,
            metrics_ref[0],
            genesis_flush_lock,
            genesis_tokens_delta,
            max_billing_client_cardinality,
            MAX_BILLING_MODEL_CARDINALITY,
            plugin,
            model_id,
            client_id,
            tokens_value,
        )

    async def handle_modality_usage(_action: str, payload: MetricsWorkerPayload) -> None:
        plugin = get_str_arg(payload, 0)
        model_id = get_str_arg(payload, 1)
        client_id = get_str_arg(payload, 2)
        if plugin is None or model_id is None or client_id is None:
            return
        record = ModalityUsageRecord(
            plugin=plugin,
            model_id=model_id,
            client_id=client_id,
            text_tokens=_get_non_negative_int_arg(payload, 3),
            audio_input_bytes=_get_non_negative_int_arg(payload, 4),
            audio_input_seconds=_get_non_negative_float_arg(payload, 5),
            audio_output_bytes=_get_non_negative_int_arg(payload, 6),
            audio_output_seconds=_get_non_negative_float_arg(payload, 7),
            image_input_count=_get_non_negative_int_arg(payload, 8),
            image_output_count=_get_non_negative_int_arg(payload, 9),
        )
        await record_modality_usage(
            lock,
            metrics_ref[0],
            max_billing_client_cardinality,
            MAX_BILLING_MODEL_CARDINALITY,
            record,
        )

    async def handle_download_speed(_action: str, payload: MetricsWorkerPayload) -> None:
        speed_value = get_float_arg(payload, 0)
        if speed_value is None:
            return
        option_values = extract_options(payload)
        source_value = option_values.get("source", "real_download")
        source = source_value if isinstance(source_value, str) and source_value else "real_download"
        await update_download_speed(
            lock,
            metrics_ref[0],
            database_hardware,
            speed_value,
            source,
        )

    async def handle_genesis_request(_action: str, _payload: MetricsWorkerPayload) -> None:
        await increment_genesis_request(genesis_flush_lock, genesis_requests_delta)

    async def handle_purge_plugin_metrics(_action: str, payload: MetricsWorkerPayload) -> None:
        plugin_name = get_str_arg(payload, 0)
        if plugin_name is None:
            return
        async with lock:
            purge_plugin_scoped_metrics(metrics_ref[0], plugin_name)

    return {
        "increment_counter": handle_increment_counter,
        "set_gauge": handle_set_gauge,
        "record_timing": handle_record_timing,
        "record_historical_metric": handle_record_historical_metric,
        "record_unique": handle_record_unique,
        "record_tokens_for_billing": handle_tokens,
        "record_modality_usage": handle_modality_usage,
        "update_download_speed_metrics": handle_download_speed,
        "increment_genesis_request": handle_genesis_request,
        "purge_plugin_metrics": handle_purge_plugin_metrics,
    }


def _get_non_negative_int_arg(payload: MetricsWorkerPayload, index: int) -> int:
    value = get_strict_int_arg(payload, index)
    return coerce_non_negative_int_strict_or_zero(value)


def _get_non_negative_float_arg(payload: MetricsWorkerPayload, index: int) -> float:
    value = get_float_arg(payload, index)
    return coerce_non_negative_float_strict_or_zero(value)
