"""SoAI - Billing and modality usage metric collectors [backend/metrics/manager/billing_usage_collectors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.metrics.keyspace_base import (
    METRIC_BLOCK_BILLING,
    METRIC_BLOCK_USAGE,
    METRIC_KEY_TOKENS_BY_CLIENT,
    METRIC_KEY_TOKENS_BY_MODEL,
    METRIC_KEY_TOKENS_BY_PLUGIN,
    METRIC_KEY_TOTAL_TOKENS_GENERATED,
    METRIC_KEY_USAGE_BY_CLIENT,
    METRIC_KEY_USAGE_BY_MODEL,
    METRIC_KEY_USAGE_BY_PLUGIN,
    METRIC_KEY_USAGE_TOTALS,
)
from core.metrics.usage import (
    MODALITY_USAGE_FIELDS,
    ModalityUsageRecord,
    create_modality_usage_counts,
)
from core.validation.integers import is_strict_int
from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "record_modality_usage",
    "record_tokens_for_billing",
)


async def record_tokens_for_billing(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    genesis_flush_lock: asyncio.Lock,
    genesis_tokens_delta: list[int],
    max_client_cardinality: int,
    max_model_cardinality: int,
    plugin: str,
    model_id: str,
    client_id: str,
    tokens: int,
) -> None:
    if tokens <= 0:
        return
    async with lock:
        billing = metrics.get(METRIC_BLOCK_BILLING)
        if not isinstance(billing, dict):
            return
        total = billing.get(METRIC_KEY_TOTAL_TOKENS_GENERATED, 0)
        total_int = int(total) if is_strict_int(total) else 0
        billing[METRIC_KEY_TOTAL_TOKENS_GENERATED] = total_int + tokens
        tokens_by_plugin = billing.get(METRIC_KEY_TOKENS_BY_PLUGIN)
        tokens_by_model = billing.get(METRIC_KEY_TOKENS_BY_MODEL)
        tokens_by_client = billing.get(METRIC_KEY_TOKENS_BY_CLIENT)
        if not (
            isinstance(tokens_by_plugin, dict)
            and isinstance(tokens_by_model, dict)
            and isinstance(tokens_by_client, dict)
        ):
            return
        plugin_raw = tokens_by_plugin.get(plugin, 0)
        model_key = _resolve_cardinality_key(
            model_id,
            counters=tokens_by_model,
            maximum=max_model_cardinality,
        )
        model_raw = tokens_by_model.get(model_key, 0)
        tokens_by_plugin[plugin] = (int(plugin_raw) if is_strict_int(plugin_raw) else 0) + tokens
        tokens_by_model[model_key] = (int(model_raw) if is_strict_int(model_raw) else 0) + tokens
        client_key = _resolve_cardinality_key(
            client_id,
            counters=tokens_by_client,
            maximum=max_client_cardinality,
        )
        client_raw = tokens_by_client.get(client_key, 0)
        tokens_by_client[client_key] = (
            int(client_raw) if is_strict_int(client_raw) else 0
        ) + tokens
    async with genesis_flush_lock:
        genesis_tokens_delta[0] += tokens


async def record_modality_usage(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    max_client_cardinality: int,
    max_model_cardinality: int,
    record: ModalityUsageRecord,
) -> None:
    if not record.has_usage():
        return
    async with lock:
        usage = metrics.get(METRIC_BLOCK_USAGE)
        if not isinstance(usage, dict):
            return
        totals = _require_usage_counts(usage, METRIC_KEY_USAGE_TOTALS)
        by_plugin = usage.get(METRIC_KEY_USAGE_BY_PLUGIN)
        by_model = usage.get(METRIC_KEY_USAGE_BY_MODEL)
        by_client = usage.get(METRIC_KEY_USAGE_BY_CLIENT)
        if not (
            isinstance(by_plugin, dict)
            and isinstance(by_model, dict)
            and isinstance(by_client, dict)
        ):
            return
        _apply_usage_counts(totals, record)
        _apply_usage_counts(_require_usage_counts(by_plugin, record.plugin), record)
        model_key = _resolve_cardinality_key(
            record.model_id,
            counters=by_model,
            maximum=max_model_cardinality,
        )
        _apply_usage_counts(_require_usage_counts(by_model, model_key), record)
        client_key = _resolve_cardinality_key(
            record.client_id,
            counters=by_client,
            maximum=max_client_cardinality,
        )
        _apply_usage_counts(_require_usage_counts(by_client, client_key), record)


def _resolve_cardinality_key(
    key: str,
    *,
    counters: dict[str, MetricValue],
    maximum: int,
) -> str:
    if maximum <= 0 or (key not in counters and len(counters) >= maximum):
        return "overflow"
    return key


def _require_usage_counts(parent: dict[str, MetricValue], key: str) -> dict[str, MetricValue]:
    value = parent.get(key)
    if isinstance(value, dict):
        _ensure_usage_fields(value)
        return value
    counts: dict[str, MetricValue] = _new_usage_counts()
    parent[key] = counts
    return counts


def _new_usage_counts() -> dict[str, MetricValue]:
    return dict(create_modality_usage_counts())


def _ensure_usage_fields(counts: dict[str, MetricValue]) -> None:
    for field in MODALITY_USAGE_FIELDS:
        if field in counts:
            continue
        if field.endswith("_seconds"):
            counts[field] = 0.0
        else:
            counts[field] = 0


def _apply_usage_counts(counts: dict[str, MetricValue], record: ModalityUsageRecord) -> None:
    _increment_int(counts, "text_tokens", record.text_tokens)
    _increment_int(counts, "audio_input_bytes", record.audio_input_bytes)
    _increment_float(counts, "audio_input_seconds", record.audio_input_seconds)
    _increment_int(counts, "audio_output_bytes", record.audio_output_bytes)
    _increment_float(counts, "audio_output_seconds", record.audio_output_seconds)
    _increment_int(counts, "image_input_count", record.image_input_count)
    _increment_int(counts, "image_output_count", record.image_output_count)


def _increment_int(counts: dict[str, MetricValue], key: str, amount: int) -> None:
    if amount <= 0:
        return
    current = counts.get(key, 0)
    counts[key] = (int(current) if is_strict_int(current) else 0) + amount


def _increment_float(counts: dict[str, MetricValue], key: str, amount: float) -> None:
    if amount <= 0.0:
        return
    current = counts.get(key, 0.0)
    base = (
        float(current)
        if isinstance(current, int | float) and not isinstance(current, bool)
        else 0.0
    )
    counts[key] = base + float(amount)
